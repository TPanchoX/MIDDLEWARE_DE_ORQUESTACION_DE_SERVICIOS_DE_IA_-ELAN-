import numpy as np

from app.schemas.video import VideoWindow, WindowConfig


class WindowBuilder:
    def build(
        self,
        frames: list[np.ndarray],
        frame_indices: list[int],
        config: WindowConfig,
    ) -> list[VideoWindow]:
        if len(frames) != len(frame_indices):
            raise ValueError("frames and frame_indices must have the same length")
        if not frames:
            return []

        windows: list[VideoWindow] = []
        start = 0
        window_id = 0

        while start < len(frames):
            end = start + config.window_size
            window_frames = frames[start:end]
            window_indices = frame_indices[start:end]

            if len(window_frames) < config.window_size:
                window_frames, window_indices = self._pad_window(
                    window_frames=window_frames,
                    window_indices=window_indices,
                    target_size=config.window_size,
                )

            stacked_window = np.stack(window_frames, axis=0)
            windows.append(
                VideoWindow(
                    window_id=window_id,
                    start_frame=window_indices[0],
                    end_frame=window_indices[-1],
                    frame_indices=window_indices,
                    frames=stacked_window,
                )
            )

            if end >= len(frames):
                break

            start += config.stride
            window_id += 1

        return windows

    def _pad_window(
        self,
        window_frames: list[np.ndarray],
        window_indices: list[int],
        target_size: int,
    ) -> tuple[list[np.ndarray], list[int]]:
        padded_frames = list(window_frames)
        padded_indices = list(window_indices)
        last_frame = padded_frames[-1]
        last_index = padded_indices[-1]

        while len(padded_frames) < target_size:
            padded_frames.append(last_frame.copy())
            padded_indices.append(last_index)

        return padded_frames, padded_indices


window_builder = WindowBuilder()
