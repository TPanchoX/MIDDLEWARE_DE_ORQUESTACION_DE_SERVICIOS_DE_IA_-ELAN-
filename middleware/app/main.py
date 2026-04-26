import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes_health import router as health_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_models import router as models_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.schemas.common import ErrorResponse
from app.services.job_service import JobNotFoundError
from app.services.model_registry_service import ModelNotFoundError


configure_logging()
logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title=settings.service_name,
    version=settings.service_version,
    description="Local FastAPI middleware for ELAN AI orchestration - Phase 1 base.",
)


@app.exception_handler(ModelNotFoundError)
async def handle_model_not_found(_: Request, exc: ModelNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error_code="model_not_found", detail=str(exc)).model_dump(),
    )


@app.exception_handler(JobNotFoundError)
async def handle_job_not_found(_: Request, exc: JobNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ErrorResponse(error_code="job_not_found", detail=str(exc)).model_dump(),
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error: %s", exc)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_code="internal_server_error",
            detail="An unexpected internal error occurred.",
        ).model_dump(),
    )


app.include_router(health_router)
app.include_router(models_router, prefix=settings.api_v1_prefix)
app.include_router(jobs_router, prefix=settings.api_v1_prefix)
