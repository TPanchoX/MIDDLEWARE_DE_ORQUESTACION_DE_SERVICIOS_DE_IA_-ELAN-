"""
Punto de entrada del middleware de orquestación ELAN–IA.

Crea la aplicación FastAPI, registra los routers (health, models, jobs,
metrics) y define los manejadores globales de excepciones que convierten
cualquier error interno en la respuesta uniforme del sistema:

    {"error_code": "CODIGO_DESCRIPTIVO", "detail": "Mensaje legible."}

Cada excepción de dominio declara su propio ``error_code`` y ``status_code``
(HTTP), de modo que ELAN, Postman o cualquier cliente pueda identificar la
causa de una falla sin revisar los logs (ver capítulo de Metodología del TIC,
Fase 1 y Fase 3).
"""
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_models import router as models_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.runners.runner_selector import RunnerSelectionError
from app.schemas.common import ErrorResponse
from app.services.docker_lifecycle_service import DockerLifecycleError
from app.services.docker_service import DockerServiceError
from app.services.job_service import JobNotFoundError
from app.services.model_registry_service import ModelRegistryError


# Configuración de logging y settings ANTES de crear la app.
# Al importarse los servicios (singletons), el registro de modelos ya escanea
# data/bootstrap_manifests/ y reconstruye el registry si es necesario.
configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    description="Middleware FastAPI local para la orquestación ELAN-IA.",
)


# ── Manejadores globales de errores ─────────────────────────────────────────
# Traducen las excepciones de dominio al formato uniforme ErrorResponse.
# Errores del registry de modelos (instalación, manifest, estado): 400/404/409.
@app.exception_handler(ModelRegistryError)
async def handle_model_registry_error(_: Request, exc: ModelRegistryError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error_code=exc.error_code, detail=str(exc)).model_dump(),
    )


# Runtime/framework no soportado por el selector de runners: 501.
@app.exception_handler(RunnerSelectionError)
async def handle_runner_selection_error(_: Request, exc: RunnerSelectionError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error_code=exc.error_code, detail=str(exc)).model_dump(),
    )


# Errores del DockerRunner durante la inferencia:
# 503 DOCKER_NOT_AVAILABLE, 404 DOCKER_IMAGE_NOT_FOUND, 502 arranque/health/
# backend, 504 DOCKER_TIMEOUT, 422 UNSUPPORTED_DOCKER_CONTRACT.
@app.exception_handler(DockerServiceError)
async def handle_docker_service_error(_: Request, exc: DockerServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error_code=exc.error_code, detail=str(exc)).model_dump(),
    )


# Errores de build/arranque durante la INSTALACIÓN de un modelo
# (normalmente ya convertidos a MODEL_PACKAGE_INVALID con rollback).
@app.exception_handler(DockerLifecycleError)
async def handle_docker_lifecycle_error(_: Request, exc: DockerLifecycleError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error_code=exc.error_code, detail=exc.detail).model_dump(),
    )



@app.exception_handler(JobNotFoundError)
async def handle_job_not_found(_: Request, exc: JobNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error_code="JOB_NOT_FOUND", detail=str(exc)).model_dump(),
    )


# Red de seguridad: cualquier error no previsto responde 500 con un mensaje
# genérico (el detalle completo queda en los logs, no se expone al cliente).
@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="INTERNAL_SERVER_ERROR",
            detail="An unexpected internal error occurred.",
        ).model_dump(),
    )


# ── Montaje de routers ──────────────────────────────────────────────────────
# /health queda en la raíz; el resto bajo el prefijo /api/v1.
app.include_router(health_router)
app.include_router(models_router, prefix=settings.api_v1_prefix)
app.include_router(jobs_router, prefix=settings.api_v1_prefix)
app.include_router(metrics_router, prefix=settings.api_v1_prefix)
