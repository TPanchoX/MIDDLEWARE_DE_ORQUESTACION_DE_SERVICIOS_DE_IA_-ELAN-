from fastapi import APIRouter, File, UploadFile

from app.schemas.common import ErrorResponse
from app.schemas.models import (
    ModelDetailResponse,
    ModelInstallResponse,
    ModelListResponse,
    ModelStatusUpdateRequest,
    ModelStatusUpdateResponse,
)
from app.services.model_registry_service import model_registry_service


router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    return model_registry_service.list_models_response()


@router.post(
    "/models/install",
    response_model=ModelInstallResponse,
    responses={
        400: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
    },
)
async def install_model(file: UploadFile = File(...)) -> ModelInstallResponse:
    content = await file.read()
    return model_registry_service.install_model_package(
        filename=file.filename or "model_package.zip",
        content=content,
    )


@router.get(
    "/models/{model_id}",
    response_model=ModelDetailResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_model(model_id: str, version: str | None = None) -> ModelDetailResponse:
    return ModelDetailResponse(model=model_registry_service.get_model(model_id=model_id, version=version))


@router.patch(
    "/models/{model_id}/status",
    response_model=ModelStatusUpdateResponse,
    responses={404: {"model": ErrorResponse}},
)
def update_model_status(
    model_id: str,
    payload: ModelStatusUpdateRequest,
    version: str | None = None,
) -> ModelStatusUpdateResponse:
    return model_registry_service.update_status(
        model_id=model_id,
        status=payload.status,
        version=version,
    )
