"""
Contratos Pydantic del registro de modelos (contrato de empaquetado del TIC).

``ModelManifest`` es la validación ejecutable del ``manifest.json`` que viaja
en la raíz de cada paquete ZIP: identidad (``model_id``/``version`` con el
patrón seguro ``[A-Za-z0-9_.-]``), tarea soportada, ``runtime`` (solo
``docker``/``container``), artefactos con rutas relativas, contratos de
entrada/salida y el bloque ``ui`` que ELAN usa para pre-poblar su panel.
``InstalledModel`` extiende el manifest con el estado de instalación que se
persiste en ``registry.json``.
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


ModelTask = Literal["video_segmentation", "video_segmentation_and_gloss_classification"]
ModelStatus = Literal["available", "disabled", "invalid"]
RuntimeMode = Literal["docker"]
RuntimeFramework = Literal["container"]

MODEL_ID_PATTERN = r"^[A-Za-z0-9_.-]+$"
MODEL_VERSION_PATTERN = r"^[A-Za-z0-9_.-]+$"


class ModelRuntime(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: RuntimeMode
    framework: RuntimeFramework
    runner: str | None = None


class ModelInputContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    media_type: Literal["video"]
    layout: str | None = Field(default=None, min_length=1)
    window_size: int | None = Field(default=None, gt=0)
    channels: int | None = Field(default=None, gt=0)
    height: int | None = Field(default=None, gt=0)
    width: int | None = Field(default=None, gt=0)
    feature_type: str | None = Field(default=None, min_length=1)
    input_dim: int | None = Field(default=None, gt=0)


class ModelOutputContract(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(min_length=1)
    classes: List[str] = Field(min_length=1)

    @field_validator("classes")
    @classmethod
    def validate_classes(cls, classes: List[str]) -> List[str]:
        if any(not item.strip() for item in classes):
            raise ValueError("classes must not contain empty values")
        return classes


class ModelUiConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    default_label: str | None = Field(default=None, min_length=1)
    default_target_tier: str | None = Field(default=None, min_length=1)
    label_mode: str | None = Field(default=None, min_length=1)
    supports_threshold: bool = False


class ModelManifest(BaseModel):
    model_config = ConfigDict(extra="allow")

    model_id: str = Field(min_length=1, pattern=MODEL_ID_PATTERN)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1, pattern=MODEL_VERSION_PATTERN)
    task: ModelTask
    runtime: ModelRuntime
    artifacts: Dict[str, str] = Field(min_length=1)
    input_contract: ModelInputContract
    output_contract: ModelOutputContract
    ui: ModelUiConfig

    @field_validator("artifacts")
    @classmethod
    def validate_artifacts(cls, artifacts: Dict[str, str]) -> Dict[str, str]:
        for key, value in artifacts.items():
            if not key.strip():
                raise ValueError("artifact keys must not be empty")
            if not value.strip():
                raise ValueError("artifact paths must not be empty")
        return artifacts


class InstalledModel(ModelManifest):
    status: ModelStatus = "available"
    installed_at: str
    install_path: Optional[str] = None
    source: Literal["builtin", "installed"] = "installed"


class RegisteredModel(BaseModel):
    model_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    task: ModelTask
    runtime: RuntimeMode
    status: ModelStatus


class ModelReference(BaseModel):
    model_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ModelListResponse(BaseModel):
    models: List[RegisteredModel]


class ModelDetailResponse(BaseModel):
    model: InstalledModel


class ModelInstallResponse(BaseModel):
    message: str
    model: InstalledModel


class ModelStatusUpdateRequest(BaseModel):
    status: Literal["available", "disabled"]


class ModelStatusUpdateResponse(BaseModel):
    message: str
    model: InstalledModel
