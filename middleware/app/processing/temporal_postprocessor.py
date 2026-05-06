from dataclasses import dataclass

from app.schemas.inference import FrameProbabilityOutput
from app.schemas.jobs import SegmentationParameters, TemporalSegment


@dataclass
class _CandidateSegment:
    start_ms: int
    end_ms: int
    confidence: float

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class TemporalPostprocessor:
    def process(
        self,
        frame_output: FrameProbabilityOutput,
        parameters: SegmentationParameters,
        default_label: str,
    ) -> list[TemporalSegment]:
        candidates = self._detect_positive_regions(
            frame_output=frame_output,
            threshold=parameters.threshold,
        )
        filtered = [
            candidate
            for candidate in candidates
            if candidate.duration_ms >= parameters.min_segment_ms
        ]
        merged = self._merge_close_segments(
            segments=filtered,
            merge_gap_ms=parameters.merge_gap_ms,
        )
        return [
            TemporalSegment(
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                label=default_label,
                confidence=round(segment.confidence, 4),
            )
            for segment in merged
        ]

    def _detect_positive_regions(
        self,
        frame_output: FrameProbabilityOutput,
        threshold: float,
    ) -> list[_CandidateSegment]:
        segments: list[_CandidateSegment] = []
        region_start: int | None = None
        region_probabilities: list[float] = []

        for frame_index, probability in enumerate(frame_output.probabilities):
            if probability >= threshold:
                if region_start is None:
                    region_start = frame_index
                region_probabilities.append(probability)
                continue

            if region_start is not None:
                segments.append(
                    self._build_segment(
                        frame_output=frame_output,
                        start_frame=region_start,
                        end_frame=frame_index,
                        probabilities=region_probabilities,
                    )
                )
                region_start = None
                region_probabilities = []

        if region_start is not None:
            segments.append(
                self._build_segment(
                    frame_output=frame_output,
                    start_frame=region_start,
                    end_frame=len(frame_output.probabilities),
                    probabilities=region_probabilities,
                )
            )

        return segments

    def _build_segment(
        self,
        frame_output: FrameProbabilityOutput,
        start_frame: int,
        end_frame: int,
        probabilities: list[float],
    ) -> _CandidateSegment:
        start_ms = self._frame_to_ms(start_frame, frame_output.fps)
        end_ms = min(
            frame_output.duration_ms,
            self._frame_to_ms(end_frame, frame_output.fps),
        )
        confidence = sum(probabilities) / len(probabilities)
        return _CandidateSegment(
            start_ms=start_ms,
            end_ms=end_ms,
            confidence=confidence,
        )

    def _merge_close_segments(
        self,
        segments: list[_CandidateSegment],
        merge_gap_ms: int,
    ) -> list[_CandidateSegment]:
        if not segments:
            return []

        merged = [segments[0]]
        for segment in segments[1:]:
            previous = merged[-1]
            gap_ms = segment.start_ms - previous.end_ms
            if gap_ms < merge_gap_ms:
                merged[-1] = self._merge_pair(previous, segment)
            else:
                merged.append(segment)
        return merged

    @staticmethod
    def _merge_pair(first: _CandidateSegment, second: _CandidateSegment) -> _CandidateSegment:
        total_duration = first.duration_ms + second.duration_ms
        if total_duration <= 0:
            confidence = max(first.confidence, second.confidence)
        else:
            confidence = (
                (first.confidence * first.duration_ms)
                + (second.confidence * second.duration_ms)
            ) / total_duration
        return _CandidateSegment(
            start_ms=first.start_ms,
            end_ms=second.end_ms,
            confidence=confidence,
        )

    @staticmethod
    def _frame_to_ms(frame_index: int, fps: float) -> int:
        return int(round(frame_index * 1000 / fps))


temporal_postprocessor = TemporalPostprocessor()
