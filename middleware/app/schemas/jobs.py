from enum import Enum
from typing import List, Literal

from pydantic import BaseModel, Field, model_validator

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


class ExecutionConfig(BaseModel):
    device_preference: Literal["auto", "cpu"] = "auto"
    runner: Literal["auto", "dummy"] = "auto"
    timeout_sec: int = Field(default=300, gt=0)


class SegmentationParameters(BaseModel):
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    window_size: int = Field(default=16, gt=0)
    stride: int = Field(default=4, gt=0)
    min_segment_ms: int = Field(default=200, gt=0)
    merge_gap_ms: int = Field(default=120, ge=0)


class SegmentVideoRequest(BaseModel):
    job_id: str = Field(min_length=1)
    media: MediaInput
    annotation: AnnotationConfig
    model: ModelReference
    execution: ExecutionConfig
    parameters: SegmentationParameters


class TemporalSegment(BaseModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    label: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_range(self) -> "TemporalSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class MediaInfo(BaseModel):
    fps: float = Field(gt=0)
    duration_ms: int = Field(gt=0)
    total_frames: int = Field(gt=0)


class ExecutionTrace(BaseModel):
    runner: str = Field(min_length=1)
    device: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    exec_ms: int = Field(ge=0)


class SegmentVideoResponse(BaseModel):
    job_id: str
    status: JobStatus
    media_info: MediaInfo
    segments: List[TemporalSegment]
    trace: ExecutionTrace
