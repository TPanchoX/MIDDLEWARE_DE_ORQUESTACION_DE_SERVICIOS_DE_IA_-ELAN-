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


configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    description="Local FastAPI middleware for ELAN AI orchestration.",
)


@app.exception_handler(ModelRegistryError)
async def handle_model_registry_error(_: Request, exc: ModelRegistryError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error_code=exc.error_code, detail=str(exc)).model_dump(),
    )


@app.exception_handler(RunnerSelectionError)
async def handle_runner_selection_error(_: Request, exc: RunnerSelectionError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error_code=exc.error_code, detail=str(exc)).model_dump(),
    )


@app.exception_handler(DockerServiceError)
async def handle_docker_service_error(_: Request, exc: DockerServiceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(error_code=exc.error_code, detail=str(exc)).model_dump(),
    )


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


app.include_router(health_router)
app.include_router(models_router, prefix=settings.api_v1_prefix)
app.include_router(jobs_router, prefix=settings.api_v1_prefix)
app.include_router(metrics_router, prefix=settings.api_v1_prefix)
