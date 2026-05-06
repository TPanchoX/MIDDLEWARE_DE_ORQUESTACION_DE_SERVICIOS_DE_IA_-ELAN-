from __future__ import annotations

from dataclasses import dataclass

import numpy as np


O_LABEL = 0
B_LABEL = 1
I_LABEL = 2


@dataclass(frozen=True)
class BioSegment:
    start_frame: int
    end_frame: int
    confidence: float

    @property
    def duration_frames(self) -> int:
        return self.end_frame - self.start_frame


def smooth_labels_majority(labels: np.ndarray, kernel_size: int = 3) -> np.ndarray:
    if labels.ndim != 1:
        raise ValueError("labels must have shape [T].")
    if kernel_size <= 1 or len(labels) == 0:
        return labels.astype(np.int64, copy=True)

    if kernel_size % 2 == 0:
        kernel_size += 1

    pad = kernel_size // 2
    padded = np.pad(labels.astype(np.int64, copy=False), (pad, pad), mode="edge")
    smoothed = np.zeros_like(labels, dtype=np.int64)
    for index in range(len(labels)):
        window = padded[index : index + kernel_size]
        counts = np.bincount(window, minlength=3)
        smoothed[index] = int(np.argmax(counts))
    return smoothed


def suppress_inner_b(labels: np.ndarray, min_i_after_b: int = 3, enabled: bool = True) -> np.ndarray:
    if labels.ndim != 1:
        raise ValueError("labels must have shape [T].")
    if not enabled or len(labels) == 0:
        return labels.astype(np.int64, copy=True)

    output = labels.astype(np.int64, copy=True)
    inside_segment = False
    for index in range(len(output)):
        if output[index] == B_LABEL:
            if inside_segment:
                output[index] = I_LABEL
            else:
                inside_segment = True
        elif output[index] == O_LABEL:
            inside_segment = False
        elif output[index] == I_LABEL and not inside_segment:
            inside_segment = True
    return output


def labels_to_segments(
    labels: np.ndarray,
    probabilities: np.ndarray | None = None,
    min_i_after_b: int = 3,
) -> list[BioSegment]:
    if labels.ndim != 1:
        raise ValueError("labels must have shape [T].")
    if probabilities is not None and (probabilities.ndim != 2 or probabilities.shape[0] != len(labels)):
        raise ValueError("probabilities must have shape [T, C].")

    segments: list[BioSegment] = []
    index = 0
    n_labels = len(labels)

    while index < n_labels:
        if labels[index] != B_LABEL:
            index += 1
            continue

        start = index
        end = index + 1
        i_count = 0
        while end < n_labels and labels[end] in (B_LABEL, I_LABEL):
            if labels[end] == I_LABEL:
                i_count += 1
            end += 1

        if i_count >= min_i_after_b:
            segments.append(_build_segment(start, end, probabilities))
        index = end

    return segments


def fill_small_gaps(segments: list[BioSegment], max_gap: int = 0) -> list[BioSegment]:
    if max_gap <= 0 or not segments:
        return list(segments)

    merged = [segments[0]]
    for segment in segments[1:]:
        previous = merged[-1]
        gap = segment.start_frame - previous.end_frame
        if 0 <= gap <= max_gap:
            merged[-1] = _merge_pair(previous, segment)
        else:
            merged.append(segment)
    return merged


def filter_short_segments(segments: list[BioSegment], min_segment_len: int = 0) -> list[BioSegment]:
    if min_segment_len <= 0:
        return list(segments)
    return [segment for segment in segments if segment.duration_frames >= min_segment_len]


def decode_segments(
    labels: np.ndarray,
    probabilities: np.ndarray | None = None,
    smooth_kernel: int = 3,
    min_segment_len: int = 4,
    max_gap_fill: int = 0,
    min_i_after_b: int = 3,
    suppress_repeated_b_inside_segment: bool = False,
) -> list[BioSegment]:
    decoded = smooth_labels_majority(labels=labels, kernel_size=smooth_kernel)
    decoded = suppress_inner_b(
        labels=decoded,
        min_i_after_b=min_i_after_b,
        enabled=suppress_repeated_b_inside_segment,
    )
    segments = labels_to_segments(labels=decoded, probabilities=probabilities, min_i_after_b=min_i_after_b)
    segments = fill_small_gaps(segments=segments, max_gap=max_gap_fill)
    return filter_short_segments(segments=segments, min_segment_len=min_segment_len)


def _build_segment(start: int, end: int, probabilities: np.ndarray | None) -> BioSegment:
    if probabilities is None or end <= start:
        confidence = 1.0
    else:
        class_probs = probabilities[start:end, [B_LABEL, I_LABEL]]
        confidence = float(np.max(class_probs, axis=1).mean()) if len(class_probs) else 0.0
    return BioSegment(start_frame=start, end_frame=end, confidence=max(0.0, min(1.0, confidence)))


def _merge_pair(first: BioSegment, second: BioSegment) -> BioSegment:
    total_duration = first.duration_frames + second.duration_frames
    if total_duration <= 0:
        confidence = max(first.confidence, second.confidence)
    else:
        confidence = (
            (first.confidence * first.duration_frames)
            + (second.confidence * second.duration_frames)
        ) / total_duration
    return BioSegment(
        start_frame=first.start_frame,
        end_frame=second.end_frame,
        confidence=max(0.0, min(1.0, confidence)),
    )
