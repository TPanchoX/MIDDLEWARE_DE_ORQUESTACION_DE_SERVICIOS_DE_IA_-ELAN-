from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

import cv2
import numpy as np

from app.processing.keypoints.keypoint_normalizer import DEFAULT_POSE_IDX, KeypointNormalizer, keypoint_normalizer


class MediaPipeKeypointError(Exception):
    error_code = "KEYPOINT_EXTRACTION_ERROR"
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class MediaPipeImportError(MediaPipeKeypointError):
    error_code = "MEDIAPIPE_IMPORT_ERROR"
    status_code = 500


class KeypointExtractionError(MediaPipeKeypointError):
    error_code = "KEYPOINT_EXTRACTION_ERROR"
    status_code = 500


class KeypointsEmptyError(MediaPipeKeypointError):
    error_code = "KEYPOINTS_EMPTY"
    status_code = 422


class InvalidKeypointShapeError(MediaPipeKeypointError):
    error_code = "INVALID_KEYPOINT_SHAPE"
    status_code = 422


@dataclass(frozen=True)
class KeypointExtractionResult:
    keypoints: np.ndarray
    fps: float
    frame_count: int
    duration_ms: int
    elapsed_ms: int


class MediaPipeKeypointExtractor:
    def __init__(self, normalizer: KeypointNormalizer | None = None) -> None:
        self.normalizer = normalizer or keypoint_normalizer

    def extract(
        self,
        video_path: str,
        pose_idx: list[int] | None = None,
        normalize: bool = True,
        raw_feature_dim: int = 178,
        final_feature_dim: int = 356,
        add_dynamic_features: bool = True,
    ) -> KeypointExtractionResult:
        started_at = perf_counter()
        selected_pose_idx = pose_idx or DEFAULT_POSE_IDX
        mp = self._import_mediapipe()

        capture = cv2.VideoCapture(str(Path(video_path)))
        try:
            if not capture.isOpened():
                raise KeypointExtractionError(f"OpenCV could not open video '{video_path}' for keypoint extraction.")

            fps = float(capture.get(cv2.CAP_PROP_FPS))
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if fps <= 0 or frame_count <= 0:
                raise KeypointExtractionError(f"Video '{video_path}' has invalid FPS or frame count metadata.")

            holistic = mp.solutions.holistic.Holistic(
                static_image_mode=False,
                model_complexity=1,
                smooth_landmarks=True,
                enable_segmentation=False,
                refine_face_landmarks=False,
            )
            try:
                rows = self._read_keypoints(
                    capture=capture,
                    holistic=holistic,
                    pose_idx=selected_pose_idx,
                    raw_feature_dim=raw_feature_dim,
                )
            finally:
                holistic.close()
        except MediaPipeKeypointError:
            raise
        except Exception as exc:
            raise KeypointExtractionError(f"MediaPipe keypoint extraction failed: {exc}") from exc
        finally:
            capture.release()

        if rows:
            keypoints = np.asarray(rows, dtype=np.float32)
        else:
            keypoints = np.zeros((0, raw_feature_dim), dtype=np.float32)
        if keypoints.ndim != 2 or keypoints.shape[1] != raw_feature_dim:
            raise InvalidKeypointShapeError(
                f"Expected raw keypoints shape [N, {raw_feature_dim}], got {tuple(keypoints.shape)}."
            )
        if normalize:
            keypoints = self.normalizer.normalize(keypoints=keypoints, pose_idx=selected_pose_idx)
        if add_dynamic_features:
            keypoints = self._add_dynamic_features(sequence=keypoints)
        if keypoints.ndim != 2 or keypoints.shape[1] != final_feature_dim:
            raise InvalidKeypointShapeError(
                f"Expected final keypoints shape [N, {final_feature_dim}], got {tuple(keypoints.shape)}."
            )

        duration_ms = max(1, int(round(frame_count * 1000 / fps)))
        return KeypointExtractionResult(
            keypoints=keypoints,
            fps=fps,
            frame_count=frame_count,
            duration_ms=duration_ms,
            elapsed_ms=self._elapsed_ms(started_at),
        )

    def _read_keypoints(
        self,
        capture: cv2.VideoCapture,
        holistic: object,
        pose_idx: list[int],
        raw_feature_dim: int,
    ) -> list[np.ndarray]:
        rows: list[np.ndarray] = []
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = holistic.process(rgb)
            rows.append(
                self._result_to_vector(
                    results=results,
                    pose_idx=pose_idx,
                    raw_feature_dim=raw_feature_dim,
                )
            )
        return rows

    def _result_to_vector(self, results: object, pose_idx: list[int], raw_feature_dim: int) -> np.ndarray:
        pose = self._extract_pose(results=getattr(results, "pose_landmarks", None), pose_idx=pose_idx)
        left_hand = self._extract_hand(getattr(results, "left_hand_landmarks", None))
        right_hand = self._extract_hand(getattr(results, "right_hand_landmarks", None))
        vector = np.concatenate([pose, left_hand, right_hand]).astype(np.float32)
        if vector.shape[0] != raw_feature_dim:
            raise InvalidKeypointShapeError(
                f"Expected one frame vector with {raw_feature_dim} values, got {vector.shape[0]}."
            )
        return vector

    @staticmethod
    def _extract_pose(results: object | None, pose_idx: list[int]) -> np.ndarray:
        values = np.zeros((len(pose_idx), 4), dtype=np.float32)
        if results is None:
            return values.reshape(-1)

        landmarks = getattr(results, "landmark", [])
        for out_index, landmark_index in enumerate(pose_idx):
            if 0 <= landmark_index < len(landmarks):
                landmark = landmarks[landmark_index]
                values[out_index] = [
                    float(landmark.x),
                    float(landmark.y),
                    float(landmark.z),
                    float(getattr(landmark, "visibility", 1.0)),
                ]
        return values.reshape(-1)

    @staticmethod
    def _extract_hand(results: object | None) -> np.ndarray:
        values = np.zeros((21, 3), dtype=np.float32)
        if results is None:
            return values.reshape(-1)

        landmarks = getattr(results, "landmark", [])
        for index, landmark in enumerate(landmarks[:21]):
            values[index] = [float(landmark.x), float(landmark.y), float(landmark.z)]
        return values.reshape(-1)

    @staticmethod
    def _import_mediapipe() -> object:
        try:
            import mediapipe as mp
        except ImportError as exc:
            raise MediaPipeImportError("The 'mediapipe' package is required for keypoint extraction.") from exc
        if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "holistic"):
            version = getattr(mp, "__version__", "unknown")
            raise MediaPipeImportError(
                "The keypoint pipeline requires MediaPipe Solutions with 'mp.solutions.holistic'. "
                f"Installed mediapipe version '{version}' does not expose that API. "
                "Run the middleware with Python 3.11 and mediapipe>=0.10.14,<0.10.22."
            )
        return mp

    @staticmethod
    def _add_dynamic_features(sequence: np.ndarray) -> np.ndarray:
        if sequence.shape[0] == 0:
            return sequence.astype(np.float32)
        deltas = np.zeros_like(sequence, dtype=np.float32)
        deltas[1:] = sequence[1:] - sequence[:-1]
        return np.concatenate([sequence, deltas], axis=1).astype(np.float32)

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))


mediapipe_keypoint_extractor = MediaPipeKeypointExtractor()
