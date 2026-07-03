"""
Contratos internos entre JobService y los runners.

``InferenceInput`` reúne todo lo que un runner necesita para ejecutar
(identidad del modelo, ruta del video, timeout, artefactos, sección
``container`` del manifest); ``InferenceOutput`` normaliza lo que el backend
devuelve (segmentos, media_info, métricas por etapa y traza del runner).
Son contratos internos: no se exponen por la API.
"""
from typing import Any, Dict, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.jobs import MediaInfo, TemporalSegment
from app.schemas.metrics import StageMetrics
from app.schemas.models import RuntimeFramework, RuntimeMode


class InferenceInput(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str = Field(min_length=1)
    media_path: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    runtime_mode: RuntimeMode
    runtime_framework: RuntimeFramework
    device_preference: Literal["auto", "cpu", "cuda"]
    runner_preference: str = Field(default="auto", min_length=1)
    timeout_sec: int = Field(gt=0)
    artifacts: Dict[str, str] = Field(default_factory=dict)
    annotation: Dict[str, object] = Field(default_factory=dict)
    parameters: Dict[str, object] = Field(default_factory=dict)
    container: Dict[str, object] = Field(default_factory=dict)
    model_install_path: str | None = None

class InferenceOutput(BaseModel):
    output_type: Literal["segments", "segments_with_gloss"] = "segments"
    segments: list[TemporalSegment] = Field(default_factory=list)
    media_info: MediaInfo | None = None
    metrics: StageMetrics = Field(default_factory=StageMetrics)
    runner_trace: Dict[str, Any] = Field(default_factory=dict)
