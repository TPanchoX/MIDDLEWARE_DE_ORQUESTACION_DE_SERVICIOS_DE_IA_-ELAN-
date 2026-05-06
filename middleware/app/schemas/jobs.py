from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.metrics import StageMetrics
from app.schemas.models import ModelReference


class JobStatus(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    PREPROCESSING = "PREPROCESSING"
    RUNNING = "RUNNING"
    POSTPROCESSING = "POSTPROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class MediaInput(BaseModel):
    path: str = Field(min_length=1)


class AnnotationConfig(BaseModel):
    target_tier: str = Field(min_length=1)
    default_label: str = Field(min_length=1)
    label_mode: str | None = Field(default=None, min_length=1)


class ExecutionConfig(BaseModel):
    device_preference: Literal["auto", "cpu", "cuda"] = "auto"
    runner: Literal["auto", "dummy", "native_pytorch", "keypoint_pipeline"] = "auto"
    timeout_sec: int = Field(default=300, gt=0)


class SegmentationParameters(BaseModel):
    model_config = ConfigDict(extra="allow")

    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    window_size: int = Field(default=16, gt=0)
    stride: int = Field(default=4, gt=0)
    min_segment_ms: int = Field(default=200, gt=0)
    merge_gap_ms: int = Field(default=120, ge=0)
    resize_width: int = Field(default=224, gt=0)
    resize_height: int = Field(default=224, gt=0)
    max_frames: int | None = Field(default=None, gt=0)
    frame_stride: int = Field(default=1, gt=0)
    bio_window_size: int = Field(default=64, gt=0)
    bio_stride: int = Field(default=32, gt=0)
    gloss_max_len: int = Field(default=72, gt=0)
    smooth_kernel: int = Field(default=3, gt=0)
    min_segment_len: int = Field(default=4, ge=0)
    max_gap_fill: int = Field(default=0, ge=0)
    min_i_after_b: int = Field(default=3, ge=0)
    suppress_repeated_b_inside_segment: bool = False
    top_k: int = Field(default=5, gt=0)


class SegmentVideoRequest(BaseModel):
    job_id: str = Field(min_length=1)
    media: MediaInput
    annotation: AnnotationConfig
    model: ModelReference
    execution: ExecutionConfig
    parameters: SegmentationParameters


class Prediction(BaseModel):
    rank: int = Field(gt=0)
    gloss_id: int
    gloss: str = Field(min_length=1)
    probability: float = Field(ge=0.0, le=1.0)


class TemporalSegment(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    segment_id: int | None = Field(default=None, gt=0)
    start_frame: int | None = Field(default=None, ge=0)
    end_frame: int | None = Field(default=None, ge=0)
    duration_frames: int | None = Field(default=None, ge=0)
    predictions: List[Prediction] | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "TemporalSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        if self.start_frame is not None and self.end_frame is not None and self.end_frame < self.start_frame:
            raise ValueError("end_frame must be greater than or equal to start_frame")
        return self


class MediaInfo(BaseModel):
    fps: float = Field(gt=0)
    duration_ms: int = Field(gt=0)
    total_frames: int = Field(gt=0)


class ExecutionTrace(BaseModel):
    runner: str = Field(min_length=1)
    device: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str | None = None
    output_type: str | None = None
    exec_ms: int = Field(ge=0)
    stages: StageMetrics = Field(default_factory=StageMetrics)
    state_history: List[str] = Field(default_factory=list)
    fps: float | None = None
    total_frames: int | None = None
    sampled_frames: int | None = None
    windows_count: int | None = None
    original_width: int | None = None
    original_height: int | None = None
    n_detected_segments: int | None = None
    keypoint_extraction_ms: int | None = Field(default=None, ge=0)
    bio_model_load_ms: int | None = Field(default=None, ge=0)
    gloss_model_load_ms: int | None = Field(default=None, ge=0)
    vocab_load_ms: int | None = Field(default=None, ge=0)
    bio_inference_ms: int | None = Field(default=None, ge=0)
    bio_postprocessing_ms: int | None = Field(default=None, ge=0)
    gloss_classification_ms: int | None = Field(default=None, ge=0)
    total_ms: int | None = Field(default=None, ge=0)


class SegmentVideoResponse(BaseModel):
    job_id: str
    status: JobStatus
    media_info: MediaInfo
    segments: List[TemporalSegment]
    trace: ExecutionTrace
