from __future__ import annotations

import numpy as np


DEFAULT_POSE_IDX = [0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28]
LEFT_SHOULDER_LANDMARK = 11
RIGHT_SHOULDER_LANDMARK = 12


class KeypointNormalizer:
    def normalize(
        self,
        keypoints: np.ndarray,
        pose_idx: list[int] | None = None,
    ) -> np.ndarray:
        if keypoints.ndim != 2 or keypoints.shape[1] != 178:
            raise ValueError("Keypoints must have shape [N, 178].")

        normalized = keypoints.astype(np.float32, copy=True)
        selected_pose_idx = pose_idx or DEFAULT_POSE_IDX
        left_pos = self._pose_position(selected_pose_idx, LEFT_SHOULDER_LANDMARK)
        right_pos = self._pose_position(selected_pose_idx, RIGHT_SHOULDER_LANDMARK)
        if left_pos is None or right_pos is None:
            return normalized

        for frame in normalized:
            left = frame[left_pos * 4 : left_pos * 4 + 3]
            right = frame[right_pos * 4 : right_pos * 4 + 3]

            center = (left + right) / 2.0
            scale = float(np.linalg.norm(left[:2] - right[:2]))
            if scale <= 1e-6:
                scale = 1.0

            self._normalize_pose(frame=frame, center=center, scale=scale)
            self._normalize_hand(frame=frame, start=52, center=center, scale=scale)
            self._normalize_hand(frame=frame, start=115, center=center, scale=scale)

        return normalized

    @staticmethod
    def _pose_position(pose_idx: list[int], landmark_index: int) -> int | None:
        try:
            return pose_idx.index(landmark_index)
        except ValueError:
            return None

    @staticmethod
    def _normalize_pose(frame: np.ndarray, center: np.ndarray, scale: float) -> None:
        pose = frame[:52].reshape(13, 4)
        pose[:, :3] = (pose[:, :3] - center) / scale

    @staticmethod
    def _normalize_hand(frame: np.ndarray, start: int, center: np.ndarray, scale: float) -> None:
        hand = frame[start : start + 63].reshape(21, 3)
        hand[:, :3] = (hand[:, :3] - center) / scale


keypoint_normalizer = KeypointNormalizer()
