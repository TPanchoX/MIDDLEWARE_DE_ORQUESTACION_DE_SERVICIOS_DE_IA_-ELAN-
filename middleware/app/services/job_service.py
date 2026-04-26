import logging
from typing import List

from app.schemas.jobs import (
    ExecutionTrace,
    JobStatus,
    MediaInfo,
    SegmentVideoRequest,
    SegmentVideoResponse,
    TemporalSegment,
)
from app.storage.memory_store import MemoryStore, memory_store
from app.services.model_registry_service import ModelRegistryService, model_registry_service


logger = logging.getLogger(__name__)


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job '{job_id}' was not found.")
        self.job_id = job_id


class JobService:
    def __init__(self, store: MemoryStore, registry_service: ModelRegistryService) -> None:
        self.store = store
        self.registry_service = registry_service

    def create_segment_video_job(self, request: SegmentVideoRequest) -> SegmentVideoResponse:
        model = self.registry_service.get_model(
            model_id=request.model.model_id,
            version=request.model.version,
        )

        logger.info(
            "Creating dummy segmentation job '%s' for model '%s'.",
            request.job_id,
            model.model_id,
        )

        media_info = MediaInfo(
            fps=25.0,
            duration_ms=10000,
            total_frames=250,
        )
        segments = self._build_dummy_segments(default_label=request.annotation.default_label)
        response = SegmentVideoResponse(
            job_id=request.job_id,
            status=JobStatus.COMPLETED,
            media_info=media_info,
            segments=segments,
            trace=ExecutionTrace(
                runner=model.runtime,
                device="cpu",
                model_id=model.model_id,
                exec_ms=50,
            ),
        )
        self.store.save_job(response)
        logger.info("Job '%s' stored with status '%s'.", response.job_id, response.status.value)
        return response

    def get_job(self, job_id: str) -> SegmentVideoResponse:
        job = self.store.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id=job_id)
        return job

    @staticmethod
    def _build_dummy_segments(default_label: str) -> List[TemporalSegment]:
        return [
            TemporalSegment(
                start_ms=1000,
                end_ms=2500,
                label=default_label,
                confidence=0.90,
            ),
            TemporalSegment(
                start_ms=4200,
                end_ms=6100,
                label=default_label,
                confidence=0.84,
            ),
        ]


job_service = JobService(store=memory_store, registry_service=model_registry_service)
