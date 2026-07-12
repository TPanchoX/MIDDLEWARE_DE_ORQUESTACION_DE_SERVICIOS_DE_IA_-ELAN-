"""
Contrato de respuesta de GET /api/v1/metrics (observabilidad del middleware).

Expone los contadores acumulados por ``MetricsService`` más el estado en vivo
de la cola (``active_jobs``/``queued_jobs`` se leen de JobQueue al momento de
la consulta). Ver TIC, Fase 4.
"""
from typing import Dict, Optional

from pydantic import BaseModel, Field


class MiddlewareMetrics(BaseModel):
    """Métricas del ciclo de vida de jobs desde el inicio del middleware.

    Todos los contadores se reinician cuando el proceso del middleware
    se reinicia (almacenamiento exclusivamente en memoria).
    """

    total_jobs: int = Field(ge=0, description="Total de jobs recibidos desde el inicio.")
    completed_jobs: int = Field(ge=0, description="Jobs que finalizaron en estado COMPLETED.")
    failed_jobs: int = Field(ge=0, description="Jobs que finalizaron en estado FAILED.")
    timeout_jobs: int = Field(
        ge=0,
        description=(
            "Jobs que excedieron execution.timeout_sec y finalizaron en estado TIMEOUT. "
            "Se contabilizan separadamente de failed_jobs para distinguir errores de latencia "
            "de errores funcionales del backend."
        ),
    )
    active_jobs: int = Field(ge=0, description="Jobs que se están ejecutando activamente en este momento.")
    queued_jobs: int = Field(
        ge=0,
        description=(
            "Jobs que están esperando un slot de concurrencia en la cola FIFO. "
            "Un valor mayor que 0 indica que el límite de concurrencia está saturado."
        ),
    )
    average_exec_ms: Optional[float] = Field(
        default=None,
        description=(
            "Tiempo promedio de ejecución (wall-clock) de los jobs completados, en milisegundos. "
            "Incluye tiempo en cola + tiempo de inferencia Docker. "
            "Null si no hay jobs completados aún."
        ),
    )
    last_exec_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description=(
            "Tiempo de ejecución del job completado más recientemente, en milisegundos. "
            "Null si no hay jobs completados aún."
        ),
    )
    error_counts: Dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Cantidad de ocurrencias de cada error_code desde el inicio del middleware. "
            "Ejemplo: {\"DOCKER_TIMEOUT\": 2, \"DOCKER_INFERENCE_ERROR\": 1}."
        ),
    )
