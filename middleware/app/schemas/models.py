from typing import List, Literal

from pydantic import BaseModel, Field


class RegisteredModel(BaseModel):
    model_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    task: Literal["video_segmentation"]
    runtime: str = Field(min_length=1)
    status: Literal["available", "unavailable"]


class ModelReference(BaseModel):
    model_id: str = Field(min_length=1)
    version: str = Field(min_length=1)


class ModelListResponse(BaseModel):
    models: List[RegisteredModel]
