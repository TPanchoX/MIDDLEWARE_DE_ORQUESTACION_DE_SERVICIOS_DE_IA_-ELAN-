import cv2
import numpy as np


class FramePreprocessor:
    def preprocess(
        self,
        frames: list[np.ndarray],
        resize_width: int = 224,
        resize_height: int = 224,
    ) -> list[np.ndarray]:
        """Return RGB float32 frames with shape (H, W, C) and values in [0.0, 1.0]."""
        processed_frames: list[np.ndarray] = []
        for frame in frames:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            resized_frame = cv2.resize(
                rgb_frame,
                (resize_width, resize_height),
                interpolation=cv2.INTER_AREA,
            )
            processed_frames.append(resized_frame.astype(np.float32) / 255.0)
        return processed_frames


frame_preprocessor = FramePreprocessor()
