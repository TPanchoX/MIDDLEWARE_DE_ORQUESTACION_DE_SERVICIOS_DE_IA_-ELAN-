from math import ceil
from time import perf_counter

from app.runners.base_runner import BaseRunner
from app.schemas.inference import FrameProbabilityOutput, InferenceInput, InferenceOutput
from app.schemas.metrics import StageMetrics


class DummyRunner(BaseRunner):
    runner_name = "dummy"
    device = "cpu"

    def run(self, request: InferenceInput) -> InferenceOutput:
        started_at = perf_counter()
        if request.video_metadata is None:
            fps = 25.0
            duration_ms = 10000
            total_frames = 250
        else:
            fps = request.video_metadata.fps
            duration_ms = request.video_metadata.duration_ms
            total_frames = request.video_metadata.total_frames

        probabilities = self._build_probabilities(
            fps=fps,
            total_frames=total_frames,
            positive_regions_ms=self._positive_regions_for_duration(duration_ms),
        )
        inference_ms = max(1, int(round((perf_counter() - started_at) * 1000)))

        frame_output = FrameProbabilityOutput(
            fps=fps,
            duration_ms=duration_ms,
            total_frames=total_frames,
            probabilities=probabilities,
        )
        return InferenceOutput(
            frame_probabilities=frame_output,
            metrics=StageMetrics(inference_ms=inference_ms),
        )

    def _build_probabilities(
        self,
        fps: float,
        total_frames: int,
        positive_regions_ms: list[tuple[int, int]],
    ) -> list[float]:
        probabilities = [self._background_probability(index) for index in range(total_frames)]

        for start_ms, end_ms in positive_regions_ms:
            start_frame = max(0, int(start_ms * fps / 1000))
            end_frame = min(total_frames, int(ceil(end_ms * fps / 1000)))
            for frame_index in range(start_frame, end_frame):
                probabilities[frame_index] = self._positive_probability(frame_index)

        return probabilities

    @staticmethod
    def _background_probability(frame_index: int) -> float:
        return round(0.03 + (frame_index % 5) * 0.01, 4)

    @staticmethod
    def _positive_probability(frame_index: int) -> float:
        return round(0.82 + (frame_index % 7) * 0.02, 4)

    @staticmethod
    def _positive_regions_for_duration(duration_ms: int) -> list[tuple[int, int]]:
        first_start = max(0, int(duration_ms * 0.10))
        first_end = max(first_start + 1, int(duration_ms * 0.25))
        second_start = max(first_end + 1, int(duration_ms * 0.45))
        second_end = max(second_start + 1, int(duration_ms * 0.65))
        return [
            (first_start, min(duration_ms, first_end)),
            (min(duration_ms, second_start), min(duration_ms, second_end)),
        ]
