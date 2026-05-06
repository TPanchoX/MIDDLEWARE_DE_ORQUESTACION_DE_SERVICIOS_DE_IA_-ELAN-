from pydantic import BaseModel, ConfigDict, Field, model_validator


class VideoMetadata(BaseModel):
    path: str = Field(min_length=1)
    fps: float = Field(gt=0)
    total_frames: int = Field(gt=0)
    duration_ms: int = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    codec: str | None = None


class FrameSamplingConfig(BaseModel):
    max_frames: int | None = Field(default=None, gt=0)
    frame_stride: int = Field(default=1, gt=0)


class WindowConfig(BaseModel):
    window_size: int = Field(gt=0)
    stride: int = Field(gt=0)


class VideoProcessingMetrics(BaseModel):
    video_loading_ms: int = Field(default=0, ge=0)
    frame_sampling_ms: int = Field(default=0, ge=0)
    preprocessing_ms: int = Field(default=0, ge=0)
    window_building_ms: int = Field(default=0, ge=0)
    total_video_processing_ms: int = Field(default=0, ge=0)


class VideoWindow(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    window_id: int = Field(ge=0)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    frame_indices: list[int] = Field(min_length=1)
    frames: object

    @model_validator(mode="after")
    def validate_range(self) -> "VideoWindow":
        if self.end_frame < self.start_frame:
            raise ValueError("end_frame must be greater than or equal to start_frame")
        return self


class VideoProcessingResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    metadata: VideoMetadata
    sampled_frame_indices: list[int]
    preprocessed_frames: list[object]
    windows: list[VideoWindow]
    metrics: VideoProcessingMetrics

    @property
    def sampled_frames_count(self) -> int:
        return len(self.sampled_frame_indices)

    @property
    def windows_count(self) -> int:
        return len(self.windows)
