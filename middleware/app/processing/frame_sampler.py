from pathlib import Path

import cv2
import numpy as np

from app.processing.video_loader import VideoEmptyOrInvalidError, VideoOpenError
from app.schemas.video import FrameSamplingConfig


class FrameSampler:
    def sample(
        self,
        video_path: str,
        config: FrameSamplingConfig,
    ) -> tuple[list[np.ndarray], list[int]]:
        capture = cv2.VideoCapture(str(Path(video_path)))
        try:
            if not capture.isOpened():
                raise VideoOpenError(f"OpenCV could not open video '{video_path}' for frame sampling.")

            frames: list[np.ndarray] = []
            frame_indices: list[int] = []
            frame_index = 0

            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                if frame_index % config.frame_stride == 0:
                    frames.append(frame)
                    frame_indices.append(frame_index)
                    if config.max_frames is not None and len(frames) >= config.max_frames:
                        break

                frame_index += 1

            if not frames:
                raise VideoEmptyOrInvalidError(f"Video '{video_path}' did not produce valid frames.")
            return frames, frame_indices
        finally:
            capture.release()


frame_sampler = FrameSampler()
