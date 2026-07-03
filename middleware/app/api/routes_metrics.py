from fastapi import APIRouter

from app.schemas.system_metrics import MiddlewareMetrics
from app.services.job_queue import job_queue
from app.services.metrics_service import metrics_service

router = APIRouter(tags=["metrics"])


@router.get(
    "/metrics",
    response_model=MiddlewareMetrics,
    summary="Métricas de tiempo de ejecución del middleware",
    description=(
        "Devuelve contadores y estadísticas de temporización recopilados desde "
        "que el middleware arrancó. Todos los valores se reinician al reiniciar "
        "el proceso (almacenamiento exclusivamente en memoria). "
        "Este endpoint se usa para validación de desempeño y pruebas de carga."
    ),
)
def get_metrics() -> MiddlewareMetrics:
    """Snapshot atómico de los contadores más el estado en vivo de la cola.

    active_jobs y queued_jobs no son contadores acumulados: se leen de
    JobQueue en el momento de la consulta (TIC, Fase 4).
    """
    data = metrics_service.snapshot(
        active_jobs=job_queue.active_count,
        queued_jobs=job_queue.queued_count,
    )
    return MiddlewareMetrics(**data)
