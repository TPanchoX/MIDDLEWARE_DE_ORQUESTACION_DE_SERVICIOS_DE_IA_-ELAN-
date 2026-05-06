from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class KeypointWindow:
    window_id: int
    start_frame: int
    end_frame: int
    frame_indices: list[int]
    values: np.ndarray


def build_windows(sequence: np.ndarray, window_size: int, stride: int) -> list[KeypointWindow]:
    if sequence.ndim != 2:
        raise ValueError("sequence must have shape [T, D].")
    if window_size <= 0 or stride <= 0:
        raise ValueError("window_size and stride must be greater than zero.")
    if len(sequence) == 0:
        return []

    windows: list[KeypointWindow] = []
    total_frames = len(sequence)

    if total_frames <= window_size:
        starts = [0]
    else:
        starts = list(range(0, total_frames - window_size + 1, stride))
        last_end = starts[-1] + window_size if starts else 0
        if last_end < total_frames:
            starts.append(total_frames - window_size)

    for window_id, start in enumerate(starts):
        end = min(start + window_size, total_frames)
        values = sequence[start:end]
        frame_indices = list(range(start, end))
        if len(values) < window_size:
            values, frame_indices = _pad_window(values=values, frame_indices=frame_indices, target_size=window_size)

        windows.append(
            KeypointWindow(
                window_id=window_id,
                start_frame=frame_indices[0],
                end_frame=frame_indices[-1],
                frame_indices=frame_indices,
                values=values.astype(np.float32, copy=False),
            )
        )
    return windows


def temporal_resample(sequence: np.ndarray, target_len: int) -> np.ndarray:
    if sequence.ndim != 2:
        raise ValueError("sequence must have shape [T, D].")
    if target_len <= 0:
        raise ValueError("target_len must be greater than zero.")
    if len(sequence) == target_len:
        return sequence

    source_positions = np.linspace(0, 1, sequence.shape[0])
    target_positions = np.linspace(0, 1, target_len)
    output = np.zeros((target_len, sequence.shape[1]), dtype=np.float32)
    for dim in range(sequence.shape[1]):
        output[:, dim] = np.interp(target_positions, source_positions, sequence[:, dim])
    return output


def prepare_gloss_tensor(sequence: np.ndarray, max_len: int) -> tuple[np.ndarray, np.ndarray]:
    if sequence.ndim != 2:
        raise ValueError("sequence must have shape [T, D].")
    if max_len <= 0:
        raise ValueError("max_len must be greater than zero.")

    if len(sequence) > max_len:
        prepared = temporal_resample(sequence, max_len)
        valid_len = max_len
    else:
        prepared = sequence
        valid_len = len(sequence)

    padded = np.zeros((max_len, sequence.shape[1]), dtype=np.float32)
    mask = np.zeros((max_len,), dtype=np.float32)
    if valid_len > 0:
        padded[:valid_len] = prepared[:valid_len]
        mask[:valid_len] = 1.0
    return padded, mask


def _pad_window(values: np.ndarray, frame_indices: list[int], target_size: int) -> tuple[np.ndarray, list[int]]:
    if len(values) == 0:
        raise ValueError("Cannot pad an empty window.")

    padded_values = np.zeros((target_size, values.shape[1]), dtype=np.float32)
    padded_values[: len(values)] = values.astype(np.float32, copy=False)
    padded_indices = list(frame_indices)

    pad_count = target_size - len(values)
    if pad_count <= 0:
        return values.astype(np.float32, copy=False), padded_indices
    return padded_values, padded_indices
