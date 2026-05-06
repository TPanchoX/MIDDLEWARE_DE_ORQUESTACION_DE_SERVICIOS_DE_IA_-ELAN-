from typing import Dict, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.jobs import MediaInfo, TemporalSegment
from app.schemas.metrics import StageMetrics
from app.schemas.models import RuntimeFramework, RuntimeMode
from app.schemas.video import VideoMetadata, VideoProcessingResult


class InferenceInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str = Field(min_length=1)
    media_path: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    runtime_mode: RuntimeMode
    runtime_framework: RuntimeFramework
    device_preference: Literal["auto", "cpu", "cuda"]
    runner_preference: Literal["auto", "dummy", "native_pytorch", "keypoint_pipeline"]
    timeout_sec: int = Field(gt=0)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    parameters: Dict[str, object] = Field(default_factory=dict)
    model_install_path: str | None = None
    video_metadata: VideoMetadata | None = None
    video_processing_result: VideoProcessingResult | None = None
    sampled_frames: int = Field(default=0, ge=0)
    windows_count: int = Field(default=0, ge=0)


class FrameProbabilityOutput(BaseModel):
    output_type: Literal["frame_probabilities"] = "frame_probabilities"
    fps: float = Field(gt=0)
    duration_ms: int = Field(gt=0)
    total_frames: int = Field(gt=0)
    probabilities: list[float] = Field(min_length=1)

    @field_validator("probabilities")
    @classmethod
    def validate_probabilities(cls, probabilities: list[float]) -> list[float]:
        for probability in probabilities:
            if probability < 0.0 or probability > 1.0:
                raise ValueError("probabilities must be between 0.0 and 1.0")
        return probabilities


class InferenceOutput(BaseModel):
    output_type: Literal["frame_probabilities", "segments_with_gloss"] = "frame_probabilities"
    frame_probabilities: FrameProbabilityOutput | None = None
    segments: list[TemporalSegment] = Field(default_factory=list)
    media_info: MediaInfo | None = None
    metrics: StageMetrics = Field(default_factory=StageMetrics)
