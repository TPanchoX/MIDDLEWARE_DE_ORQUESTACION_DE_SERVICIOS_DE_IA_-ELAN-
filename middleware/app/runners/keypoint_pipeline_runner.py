from __future__ import annotations

import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import torch

from app.processing.bio_postprocessor import BioSegment, decode_segments
from app.processing.keypoints.keypoint_sequence_utils import build_windows, prepare_gloss_tensor
from app.processing.keypoints.mediapipe_keypoint_extractor import MediaPipeKeypointExtractor, mediapipe_keypoint_extractor
from app.runners.base_runner import BaseRunner
from app.runners.bio_gloss_pipeline_config import BioGlossPipelineConfig
from app.runners.model_architectures import BioSegmenterBiLSTM, KeypointTransformerClassifierV11
from app.schemas.inference import InferenceInput, InferenceOutput
from app.schemas.jobs import MediaInfo, Prediction, TemporalSegment
from app.schemas.metrics import StageMetrics


class KeypointPipelineRunnerError(Exception):
    error_code = "KEYPOINT_PIPELINE_ERROR"
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ModelArtifactMissingError(KeypointPipelineRunnerError):
    error_code = "MODEL_ARTIFACT_MISSING"
    status_code = 400


class VocabNotFoundError(KeypointPipelineRunnerError):
    error_code = "VOCAB_NOT_FOUND"
    status_code = 400


class VocabInvalidError(KeypointPipelineRunnerError):
    error_code = "VOCAB_INVALID"
    status_code = 422


class BioModelLoadError(KeypointPipelineRunnerError):
    error_code = "BIO_MODEL_LOAD_ERROR"
    status_code = 409


class GlossModelLoadError(KeypointPipelineRunnerError):
    error_code = "GLOSS_MODEL_LOAD_ERROR"
    status_code = 409


class BioInferenceError(KeypointPipelineRunnerError):
    error_code = "BIO_INFERENCE_ERROR"
    status_code = 500


class GlossInferenceError(KeypointPipelineRunnerError):
    error_code = "GLOSS_INFERENCE_ERROR"
    status_code = 500


class InvalidKeypointShapeError(KeypointPipelineRunnerError):
    error_code = "INVALID_KEYPOINT_SHAPE"
    status_code = 422


class CudaNotAvailableError(KeypointPipelineRunnerError):
    error_code = "CUDA_NOT_AVAILABLE"
    status_code = 409


class KeypointPipelineRunner(BaseRunner):
    runner_name = "keypoint_pipeline"

    def __init__(self, extractor: MediaPipeKeypointExtractor | None = None) -> None:
        self.extractor = extractor or mediapipe_keypoint_extractor
        self.device = "cpu"

    def run(self, request: InferenceInput) -> InferenceOutput:
        total_started_at = perf_counter()
        device = self._select_device(request.device_preference)
        self.device = device.type

        bio_weights_path = self._resolve_artifact(request=request, artifact_name="bio_weights")
        gloss_weights_path = self._resolve_artifact(request=request, artifact_name="gloss_weights")
        vocab_path = self._resolve_artifact(request=request, artifact_name="vocab", missing_error=VocabNotFoundError)
        config_path = self._resolve_artifact(request=request, artifact_name="pipeline_config")

        raw_config = self._load_pipeline_config(config_path=config_path)
        config = self._merge_config(config=raw_config, request=request)

        vocab_started_at = perf_counter()
        class_ids, id_to_gloss = self._load_vocab(vocab_path=vocab_path)
        vocab_load_ms = self._elapsed_ms(vocab_started_at)

        bio_model_load_started_at = perf_counter()
        bio_model = self._load_bio_model(weights_path=bio_weights_path, config=config, device=device)
        bio_model_load_ms = self._elapsed_ms(bio_model_load_started_at)

        gloss_model_load_started_at = perf_counter()
        gloss_model = self._load_gloss_model(
            weights_path=gloss_weights_path,
            num_classes=len(class_ids),
            config=config,
            device=device,
        )
        gloss_model_load_ms = self._elapsed_ms(gloss_model_load_started_at)

        extraction_result = self.extractor.extract(
            video_path=request.media_path,
            pose_idx=list(config.pose_idx),
            normalize=True,
            raw_feature_dim=config.raw_feature_dim,
            final_feature_dim=config.final_feature_dim,
            add_dynamic_features=config.add_dynamic_features,
        )
        keypoints = extraction_result.keypoints
        if keypoints.ndim != 2 or keypoints.shape[1] != config.final_feature_dim:
            raise InvalidKeypointShapeError(
                f"Expected keypoints shape [N, {config.final_feature_dim}], got {tuple(keypoints.shape)}."
            )
        if len(keypoints) == 0:
            raise InvalidKeypointShapeError("Keypoint extraction returned zero frames.")

        bio_inference_started_at = perf_counter()
        bio_probabilities = self._run_bio_inference(
            model=bio_model,
            keypoints=keypoints,
            window_size=config.bio_window_size,
            stride=config.bio_stride,
            num_bio_classes=config.num_bio_classes,
            device=device,
        )
        bio_inference_ms = self._elapsed_ms(bio_inference_started_at)
        pred_labels = np.argmax(bio_probabilities, axis=1).astype(np.int64)

        bio_postprocessing_started_at = perf_counter()
        bio_segments = decode_segments(
            labels=pred_labels,
            probabilities=bio_probabilities,
            smooth_kernel=config.smooth_kernel,
            min_segment_len=config.min_segment_len,
            max_gap_fill=config.max_gap_fill,
            min_i_after_b=config.min_i_after_b,
            suppress_repeated_b_inside_segment=config.suppress_repeated_b_inside_segment,
        )
        bio_postprocessing_ms = self._elapsed_ms(bio_postprocessing_started_at)

        gloss_classification_started_at = perf_counter()
        segments = self._classify_segments(
            model=gloss_model,
            keypoints=keypoints,
            bio_segments=bio_segments,
            class_ids=class_ids,
            id_to_gloss=id_to_gloss,
            fps=extraction_result.fps,
            duration_ms=extraction_result.duration_ms,
            max_len=config.gloss_max_len,
            top_k=config.top_k,
            device=device,
        )
        gloss_classification_ms = self._elapsed_ms(gloss_classification_started_at) if bio_segments else 0

        total_ms = self._elapsed_ms(total_started_at)
        return InferenceOutput(
            output_type="segments_with_gloss",
            segments=segments,
            media_info=MediaInfo(
                fps=extraction_result.fps,
                duration_ms=extraction_result.duration_ms,
                total_frames=extraction_result.frame_count,
            ),
            metrics=StageMetrics(
                keypoint_extraction_ms=extraction_result.elapsed_ms,
                bio_model_load_ms=bio_model_load_ms,
                gloss_model_load_ms=gloss_model_load_ms,
                vocab_load_ms=vocab_load_ms,
                bio_inference_ms=bio_inference_ms,
                bio_postprocessing_ms=bio_postprocessing_ms,
                gloss_classification_ms=gloss_classification_ms,
                inference_ms=bio_inference_ms + gloss_classification_ms,
                total_ms=total_ms,
            ),
        )

    def _run_bio_inference(
        self,
        model: BioSegmenterBiLSTM,
        keypoints: np.ndarray,
        window_size: int,
        stride: int,
        num_bio_classes: int,
        device: torch.device,
    ) -> np.ndarray:
        windows = build_windows(sequence=keypoints, window_size=window_size, stride=stride)
        if not windows:
            raise BioInferenceError("BIO inference requires at least one keypoint window.")

        probability_sums = np.zeros((len(keypoints), num_bio_classes), dtype=np.float32)
        count_sums = np.zeros((len(keypoints),), dtype=np.float32)

        try:
            model.eval()
            for window in windows:
                start = window.frame_indices[0]
                end = window.frame_indices[-1] + 1
                seq_len = end - start

                tensor = torch.tensor(window.values, dtype=torch.float32).unsqueeze(0).to(device)
                with torch.no_grad():
                    output = model(tensor)
                    logits = self._extract_logits(output=output, error_type=BioInferenceError)
                    if logits.ndim != 3 or logits.shape[-1] != num_bio_classes:
                        raise BioInferenceError(
                            f"BIO model output must have shape [B, T, {num_bio_classes}]."
                        )
                    probabilities = torch.softmax(logits, dim=-1)[0].detach().cpu().numpy()

                probability_sums[start:end] += probabilities[:seq_len]
                count_sums[start:end] += 1.0
        except KeypointPipelineRunnerError:
            raise
        except Exception as exc:
            raise BioInferenceError(f"BIO inference failed: {exc}") from exc

        return probability_sums / np.maximum(count_sums[:, None], 1e-8)

    def _classify_segments(
        self,
        model: KeypointTransformerClassifierV11,
        keypoints: np.ndarray,
        bio_segments: list[BioSegment],
        class_ids: list[int],
        id_to_gloss: dict[int, str],
        fps: float,
        duration_ms: int,
        max_len: int,
        top_k: int,
        device: torch.device,
    ) -> list[TemporalSegment]:
        output_segments: list[TemporalSegment] = []
        if not bio_segments:
            return output_segments

        model.eval()
        for segment_index, bio_segment in enumerate(bio_segments, start=1):
            sequence = keypoints[bio_segment.start_frame : bio_segment.end_frame]
            if len(sequence) == 0:
                continue
            prepared, mask = prepare_gloss_tensor(sequence=sequence, max_len=max_len)
            try:
                x = torch.from_numpy(prepared).unsqueeze(0).to(device=device, dtype=torch.float32)
                mask_tensor = torch.from_numpy(mask).unsqueeze(0).to(device=device)
                with torch.no_grad():
                    output = model(x, mask=mask_tensor)
                    logits = self._extract_logits(output=output, error_type=GlossInferenceError)
                    if logits.ndim != 2 or logits.shape[1] != len(class_ids):
                        raise GlossInferenceError("Gloss model output must have shape [B, num_classes].")
                    probabilities = torch.softmax(logits, dim=1)[0].detach().cpu().numpy()
                    top_indices = np.argsort(-probabilities)[: min(top_k, len(class_ids))]
                    top_probabilities = probabilities[top_indices]
            except KeypointPipelineRunnerError:
                raise
            except Exception as exc:
                raise GlossInferenceError(f"Gloss classification failed: {exc}") from exc

            predictions = self._build_predictions(
                probabilities=top_probabilities,
                indices=top_indices,
                class_ids=class_ids,
                id_to_gloss=id_to_gloss,
            )
            if not predictions:
                continue
            top1 = predictions[0]
            output_segments.append(
                TemporalSegment(
                    segment_id=segment_index,
                    start_ms=self._frame_to_ms(bio_segment.start_frame, fps),
                    end_ms=self._frame_to_ms(bio_segment.end_frame, fps),
                    label=top1.gloss,
                    confidence=float(top1.probability),
                    start_frame=bio_segment.start_frame,
                    end_frame=bio_segment.end_frame,
                    duration_frames=bio_segment.duration_frames,
                    predictions=predictions,
                )
            )
        return output_segments

    def _load_bio_model(
        self,
        weights_path: Path,
        config: BioGlossPipelineConfig,
        device: torch.device,
    ) -> BioSegmenterBiLSTM:
        model = BioSegmenterBiLSTM(
            input_dim=config.final_feature_dim,
            hidden_dim=config.bio_hidden_dim,
            num_layers=config.bio_num_layers,
            dropout=config.bio_dropout,
            num_classes=config.num_bio_classes,
        )
        state_dict = self._load_state_dict(weights_path=weights_path, error_type=BioModelLoadError)
        try:
            model.load_state_dict(state_dict, strict=True)
        except RuntimeError as exc:
            raise BioModelLoadError("BIO weights are not compatible with BioSegmenterBiLSTM.") from exc
        return model.to(device)

    def _load_gloss_model(
        self,
        weights_path: Path,
        num_classes: int,
        config: BioGlossPipelineConfig,
        device: torch.device,
    ) -> KeypointTransformerClassifierV11:
        model = KeypointTransformerClassifierV11(
            input_dim=config.final_feature_dim,
            num_classes=num_classes,
            d_model=config.gloss_d_model,
            nhead=config.gloss_nhead,
            num_layers=config.gloss_num_layers,
            dim_feedforward=config.gloss_dim_feedforward,
            dropout=config.gloss_dropout,
            max_len=config.gloss_positional_max_len,
        )
        state_dict = self._load_state_dict(weights_path=weights_path, error_type=GlossModelLoadError)
        try:
            model.load_state_dict(state_dict, strict=True)
        except RuntimeError as exc:
            raise GlossModelLoadError(
                "Gloss weights are not compatible with KeypointTransformerClassifierV11."
            ) from exc
        return model.to(device)

    def _load_state_dict(self, weights_path: Path, error_type: type[KeypointPipelineRunnerError]) -> dict[str, torch.Tensor]:
        try:
            checkpoint = torch.load(weights_path, map_location="cpu", weights_only=True)
        except TypeError:
            try:
                checkpoint = torch.load(weights_path, map_location="cpu")
            except Exception as exc:
                raise error_type(f"Could not load weights from '{weights_path}': {exc}") from exc
        except Exception as exc:
            raise error_type(f"Could not load weights from '{weights_path}': {exc}") from exc

        if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
            checkpoint = checkpoint["state_dict"]
        if not isinstance(checkpoint, dict):
            raise error_type("PyTorch artifact must contain a state_dict.")

        state_dict: dict[str, torch.Tensor] = {}
        for key, value in checkpoint.items():
            if not isinstance(value, torch.Tensor):
                raise error_type("PyTorch state_dict contains non-tensor values.")
            state_dict[key.removeprefix("module.")] = value
        return state_dict

    def _load_vocab(self, vocab_path: Path) -> tuple[list[int], dict[int, str]]:
        if not vocab_path.exists():
            raise VocabNotFoundError(f"Vocabulary artifact '{vocab_path}' was not found.")
        try:
            vocab = pd.read_csv(vocab_path)
        except Exception as exc:
            raise VocabInvalidError(f"Vocabulary CSV could not be read: {exc}") from exc

        required_columns = {"gloss_id", "gloss"}
        if not required_columns.issubset(vocab.columns):
            raise VocabInvalidError("Vocabulary CSV must contain columns 'gloss_id' and 'gloss'.")
        if vocab.empty:
            raise VocabInvalidError("Vocabulary CSV must contain at least one gloss.")

        try:
            class_ids = [int(value) for value in vocab["gloss_id"].tolist()]
            glosses = [str(value).strip() for value in vocab["gloss"].tolist()]
        except Exception as exc:
            raise VocabInvalidError("Vocabulary gloss_id values must be integers.") from exc
        if any(not gloss for gloss in glosses):
            raise VocabInvalidError("Vocabulary gloss values must not be empty.")

        id_to_gloss = dict(zip(class_ids, glosses))
        if len(id_to_gloss) != len(class_ids):
            raise VocabInvalidError("Vocabulary gloss_id values must be unique.")
        return class_ids, id_to_gloss

    def _load_pipeline_config(self, config_path: Path) -> dict[str, Any]:
        try:
            raw_config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ModelArtifactMissingError(f"Pipeline config could not be read from '{config_path}': {exc}") from exc
        if not isinstance(raw_config, dict):
            raise ModelArtifactMissingError("Pipeline config must be a JSON object.")
        return raw_config

    def _merge_config(self, config: dict[str, Any], request: InferenceInput) -> BioGlossPipelineConfig:
        try:
            return BioGlossPipelineConfig.from_sources(
                artifact_config=config,
                request_parameters=request.parameters,
            )
        except (TypeError, ValueError) as exc:
            raise ModelArtifactMissingError(f"Pipeline config is invalid: {exc}") from exc

    def _resolve_artifact(
        self,
        request: InferenceInput,
        artifact_name: str,
        missing_error: type[KeypointPipelineRunnerError] = ModelArtifactMissingError,
    ) -> Path:
        if request.model_install_path is None:
            raise ModelArtifactMissingError("Installed model path is required for keypoint pipeline execution.")
        artifact_path = request.artifacts.get(artifact_name)
        if artifact_path is None:
            raise missing_error(f"Model manifest must declare artifacts.{artifact_name}.")

        install_path = Path(request.model_install_path).resolve()
        resolved = (install_path / artifact_path).resolve()
        try:
            resolved.relative_to(install_path)
        except ValueError as exc:
            raise ModelArtifactMissingError("Resolved artifact path escapes the installed model directory.") from exc
        if not resolved.exists():
            raise missing_error(f"Artifact '{artifact_name}' declared at '{artifact_path}' was not found.")
        return resolved

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
    def _aggregate_bio_probabilities(
        window_probabilities: np.ndarray,
        frame_indices: list[list[int]],
        total_frames: int,
    ) -> np.ndarray:
        sums = np.zeros((total_frames, 3), dtype=np.float32)
        counts = np.zeros((total_frames,), dtype=np.float32)
        for probabilities, indices in zip(window_probabilities, frame_indices):
            for probability, frame_index in zip(probabilities, indices):
                if 0 <= frame_index < total_frames:
                    sums[frame_index] += probability.astype(np.float32)
                    counts[frame_index] += 1.0
        counts = np.maximum(counts, 1.0)
        return sums / counts[:, None]

    @staticmethod
    def _extract_logits(output: object, error_type: type[KeypointPipelineRunnerError]) -> torch.Tensor:
        if isinstance(output, dict) and isinstance(output.get("logits"), torch.Tensor):
            return output["logits"]
        if isinstance(output, torch.Tensor):
            return output
        raise error_type("Model output must be a tensor or a dict containing 'logits'.")

    @staticmethod
    def _build_predictions(
        probabilities: np.ndarray,
        indices: np.ndarray,
        class_ids: list[int],
        id_to_gloss: dict[int, str],
    ) -> list[Prediction]:
        predictions: list[Prediction] = []
        for rank, (probability, class_index) in enumerate(zip(probabilities, indices), start=1):
            gloss_id = int(class_index)
            predictions.append(
                Prediction(
                    rank=rank,
                    gloss_id=gloss_id,
                    gloss=id_to_gloss[gloss_id],
                    probability=float(probability),
                )
            )
        return predictions

    @staticmethod
    def _frame_to_ms(frame_index: int, fps: float) -> int:
        return int(round(frame_index * 1000 / fps))

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))
