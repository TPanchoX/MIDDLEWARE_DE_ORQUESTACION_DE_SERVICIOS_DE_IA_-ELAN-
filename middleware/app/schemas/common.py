from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    service: str
    version: str


class ErrorResponse(BaseModel):
    error_code: str
    detail: str
