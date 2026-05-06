from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import torch

from app.processing.probability_aggregator import ProbabilityAggregator, probability_aggregator
from app.runners.base_runner import BaseRunner
from app.runners.model_architectures import VideoBinarySegmenter
from app.schemas.inference import FrameProbabilityOutput, InferenceInput, InferenceOutput
from app.schemas.metrics import StageMetrics


class PyTorchRunnerError(Exception):
    error_code = "PYTORCH_INFERENCE_ERROR"
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ModelLoadError(PyTorchRunnerError):
    error_code = "MODEL_LOAD_ERROR"
    status_code = 400


class ModelArchitectureMismatchError(PyTorchRunnerError):
    error_code = "MODEL_ARCHITECTURE_MISMATCH"
    status_code = 409


class CudaNotAvailableError(PyTorchRunnerError):
    error_code = "CUDA_NOT_AVAILABLE"
    status_code = 409


class InvalidTensorShapeError(PyTorchRunnerError):
    error_code = "INVALID_TENSOR_SHAPE"
    status_code = 422


class NativePyTorchRunner(BaseRunner):
    runner_name = "native_pytorch"

    def __init__(self, aggregator: ProbabilityAggregator | None = None) -> None:
        self.aggregator = aggregator or probability_aggregator
        self.device = "cpu"

    def run(self, request: InferenceInput) -> InferenceOutput:
        if request.video_processing_result is None:
            raise ModelLoadError("NativePyTorchRunner requires a VideoProcessingResult.")

        selected_device = self._select_device(request.device_preference)
        self.device = selected_device.type

        model_load_started_at = perf_counter()
        model = self._load_model(request=request, device=selected_device)
        model_load_ms = self._elapsed_ms(model_load_started_at)

        tensor_started_at = perf_counter()
        input_tensor = self._windows_to_tensor(request=request, device=selected_device)
        tensor_conversion_ms = self._elapsed_ms(tensor_started_at)

        inference_started_at = perf_counter()
        try:
            model.eval()
            with torch.no_grad():
                logits = model(input_tensor)
                logits = self._normalize_logits_shape(logits=logits, expected_windows=len(request.video_processing_result.windows))
                window_probabilities_tensor = torch.sigmoid(logits)
        except InvalidTensorShapeError:
            raise
        except Exception as exc:
            raise PyTorchRunnerError(f"PyTorch inference failed: {exc}") from exc
        inference_ms = self._elapsed_ms(inference_started_at)

        aggregation_started_at = perf_counter()
        window_probabilities = window_probabilities_tensor.detach().cpu().numpy().tolist()
        window_frame_indices = [window.frame_indices for window in request.video_processing_result.windows]
        probabilities, aggregation_ms = self.aggregator.aggregate(
            window_probabilities=window_probabilities,
            window_frame_indices=window_frame_indices,
            total_frames=request.video_processing_result.metadata.total_frames,
        )
        aggregation_ms = max(aggregation_ms, self._elapsed_ms(aggregation_started_at))

        frame_output = FrameProbabilityOutput(
            fps=request.video_processing_result.metadata.fps,
            duration_ms=request.video_processing_result.metadata.duration_ms,
            total_frames=request.video_processing_result.metadata.total_frames,
            probabilities=probabilities,
        )
        return InferenceOutput(
            frame_probabilities=frame_output,
            metrics=StageMetrics(
                model_load_ms=model_load_ms,
                tensor_conversion_ms=tensor_conversion_ms,
                inference_ms=inference_ms,
                aggregation_ms=aggregation_ms,
            ),
        )

    def _load_model(self, request: InferenceInput, device: torch.device) -> VideoBinarySegmenter:
        weights_path = self._resolve_weights_path(request=request)
        try:
            checkpoint = torch.load(weights_path, map_location=device, weights_only=True)
        except TypeError:
            try:
                checkpoint = torch.load(weights_path, map_location=device)
            except Exception as exc:
                raise ModelLoadError(f"Could not load PyTorch weights from '{weights_path}': {exc}") from exc
        except Exception as exc:
            raise ModelLoadError(f"Could not load PyTorch weights from '{weights_path}': {exc}") from exc

        state_dict = self._extract_state_dict(checkpoint=checkpoint)
        model = VideoBinarySegmenter()
        try:
            model.load_state_dict(state_dict, strict=True)
        except RuntimeError as exc:
            raise ModelArchitectureMismatchError(
                "Installed PyTorch weights are not compatible with VideoBinarySegmenter."
            ) from exc
        return model.to(device)

    def _resolve_weights_path(self, request: InferenceInput) -> Path:
        if request.model_install_path is None:
            raise ModelLoadError("Installed model path is required for native PyTorch execution.")

        artifact_path = request.artifacts.get("weights")
        if artifact_path is None:
            raise ModelLoadError("Model manifest must declare artifacts.weights for native PyTorch execution.")

        install_path = Path(request.model_install_path).resolve()
        weights_path = (install_path / artifact_path).resolve()
        try:
            weights_path.relative_to(install_path)
        except ValueError as exc:
            raise ModelLoadError("Resolved weights path escapes the installed model directory.") from exc
        if not weights_path.exists():
            raise ModelLoadError(f"PyTorch weights artifact '{artifact_path}' was not found.")
        return weights_path

    def _extract_state_dict(self, checkpoint: Any) -> dict[str, torch.Tensor]:
        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            checkpoint = checkpoint["state_dict"]
        if not isinstance(checkpoint, dict):
            raise ModelLoadError("PyTorch artifact must contain a state_dict.")

        normalized: dict[str, torch.Tensor] = {}
        for key, value in checkpoint.items():
            if not isinstance(value, torch.Tensor):
                raise ModelLoadError("PyTorch state_dict contains non-tensor values.")
            normalized[key.removeprefix("module.")] = value
        return normalized

    def _windows_to_tensor(self, request: InferenceInput, device: torch.device) -> torch.Tensor:
        assert request.video_processing_result is not None
        window_arrays: list[np.ndarray] = []
        for window in request.video_processing_result.windows:
            window_array = np.asarray(window.frames, dtype=np.float32)
            if window_array.ndim != 4:
                raise InvalidTensorShapeError("Each video window must have shape [T, H, W, C].")
            if window_array.shape[-1] != 3:
                raise InvalidTensorShapeError("Each video window must have 3 channels in RGB layout.")
            window_arrays.append(np.transpose(window_array, (0, 3, 1, 2)))

        if not window_arrays:
            raise InvalidTensorShapeError("NativePyTorchRunner requires at least one video window.")

        batch = np.stack(window_arrays, axis=0)
        return torch.from_numpy(batch).to(device=device, dtype=torch.float32)

    def _normalize_logits_shape(self, logits: torch.Tensor, expected_windows: int) -> torch.Tensor:
        if logits.ndim == 3 and logits.shape[-1] == 1:
            logits = logits.squeeze(-1)
        if logits.ndim != 2:
            raise InvalidTensorShapeError("PyTorch model output must have shape [B, T] or [B, T, 1].")
        if logits.shape[0] != expected_windows:
            raise InvalidTensorShapeError("PyTorch model output batch size does not match windows count.")
        return logits

    def _select_device(self, preference: str) -> torch.device:
        if preference == "cpu":
            return torch.device("cpu")
        if preference == "cuda":
            if not torch.cuda.is_available():
                raise CudaNotAvailableError("CUDA was requested but is not available.")
            return torch.device("cuda")
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))
