"""Schemas comunes: respuesta de salud y formato uniforme de error del middleware."""
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Respuesta de GET /health: estado, nombre y versión del servicio."""

    status: str = Field(default="ok")
    service: str
    version: str


class ErrorResponse(BaseModel):
    """Formato uniforme de error: {"error_code": "...", "detail": "..."}.

    El cliente Java de ELAN siempre puede leer el campo ``detail`` sin
    importar de qué capa provenga el fallo (registry, Docker o backend).
    """

    error_code: str
    detail: str
