from pathlib import Path

import cv2

from app.schemas.video import VideoMetadata


class VideoProcessingError(Exception):
    error_code = "VIDEO_PROCESSING_ERROR"
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class InvalidVideoPathError(VideoProcessingError):
    error_code = "INVALID_VIDEO_PATH"
    status_code = 400


class VideoNotFoundError(VideoProcessingError):
    error_code = "VIDEO_NOT_FOUND"
    status_code = 404


class VideoOpenError(VideoProcessingError):
    error_code = "VIDEO_OPEN_ERROR"
    status_code = 400


class VideoEmptyOrInvalidError(VideoProcessingError):
    error_code = "VIDEO_EMPTY_OR_INVALID"
    status_code = 422


class VideoLoader:
    def load_metadata(self, video_path: str) -> VideoMetadata:
        path = self._validate_path(video_path)
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise VideoOpenError(f"OpenCV could not open video '{video_path}'.")

            fps = float(capture.get(cv2.CAP_PROP_FPS))
            total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

            if fps <= 0:
                raise VideoOpenError(f"Video '{video_path}' has invalid FPS metadata.")
            if total_frames <= 0 or width <= 0 or height <= 0:
                raise VideoEmptyOrInvalidError(f"Video '{video_path}' has no valid frames or dimensions.")

            duration_ms = max(1, int(round(total_frames * 1000 / fps)))
            return VideoMetadata(
                path=str(path),
                fps=fps,
                total_frames=total_frames,
                duration_ms=duration_ms,
                width=width,
                height=height,
                codec=self._read_codec(capture),
            )
        finally:
            capture.release()

    def _validate_path(self, video_path: str) -> Path:
        if not video_path or not video_path.strip():
            raise InvalidVideoPathError("Video path must not be empty.")

        path = Path(video_path).expanduser()
        if not path.exists():
            raise VideoNotFoundError(f"Video file '{video_path}' was not found.")
        if not path.is_file():
            raise InvalidVideoPathError(f"Video path '{video_path}' is not a file.")
        return path.resolve()

    @staticmethod
    def _read_codec(capture: cv2.VideoCapture) -> str | None:
        codec_value = int(capture.get(cv2.CAP_PROP_FOURCC))
        if codec_value <= 0:
            return None
        return "".join(chr((codec_value >> 8 * index) & 0xFF) for index in range(4)).strip() or None


video_loader = VideoLoader()
