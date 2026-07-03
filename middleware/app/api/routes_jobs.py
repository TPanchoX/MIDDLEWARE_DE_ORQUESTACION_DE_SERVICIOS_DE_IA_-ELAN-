from fastapi import APIRouter

from app.schemas.common import ErrorResponse
from app.schemas.jobs import SegmentVideoRequest, SegmentVideoResponse
from app.services.job_service import job_service


router = APIRouter(tags=["jobs"])


@router.post(
    "/jobs/segment-video",
    response_model=SegmentVideoResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        409: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
        501: {"model": ErrorResponse},
    },
)
def create_segment_video_job(payload: SegmentVideoRequest) -> SegmentVideoResponse:
    """Ejecuta una inferencia sobre un video (contrato ELAN → middleware).

    Manejador SÍNCRONO a propósito: si no hay slots de concurrencia, el hilo
    queda bloqueado en la cola FIFO (JobQueue) hasta su turno, sin afectar a
    los endpoints de gestión que atienden otros hilos del pool de Uvicorn.
    """
    return job_service.create_segment_video_job(request=payload)


@router.get(
    "/jobs/{job_id}",
    response_model=SegmentVideoResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_job(job_id: str) -> SegmentVideoResponse:
    """Recupera el resultado de un job completado (almacén en memoria por sesión)."""
    return job_service.get_job(job_id=job_id)
