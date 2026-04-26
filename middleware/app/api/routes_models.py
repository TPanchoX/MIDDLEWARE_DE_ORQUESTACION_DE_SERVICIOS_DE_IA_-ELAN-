from fastapi import APIRouter

from app.schemas.models import ModelListResponse
from app.services.model_registry_service import model_registry_service


router = APIRouter(tags=["models"])


@router.get("/models", response_model=ModelListResponse)
def list_models() -> ModelListResponse:
    return ModelListResponse(models=model_registry_service.list_models())
