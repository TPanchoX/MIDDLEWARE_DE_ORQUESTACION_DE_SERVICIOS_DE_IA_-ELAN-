from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.common import HealthResponse


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Comprobación de disponibilidad del middleware (escenarios E-01/E-02).

    Devuelve estado, nombre y versión del servicio. ELAN lo usa desde el
    botón "Probar conexión" y sigue respondiendo aunque haya una inferencia
    larga en ejecución.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.service_version,
    )
