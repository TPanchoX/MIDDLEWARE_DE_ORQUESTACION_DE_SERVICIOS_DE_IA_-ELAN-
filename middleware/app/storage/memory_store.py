from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional

from app.schemas.jobs import SegmentVideoResponse
from app.schemas.models import RegisteredModel


@dataclass
class MemoryStore:
    models: Dict[str, RegisteredModel] = field(default_factory=dict)
    jobs: Dict[str, SegmentVideoResponse] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def save_model(self, model: RegisteredModel) -> None:
        with self._lock:
            self.models[model.model_id] = model

    def list_models(self) -> List[RegisteredModel]:
        with self._lock:
            return list(self.models.values())

    def get_model(self, model_id: str) -> Optional[RegisteredModel]:
        with self._lock:
            return self.models.get(model_id)

    def save_job(self, job: SegmentVideoResponse) -> None:
        with self._lock:
            self.jobs[job.job_id] = job

    def get_job(self, job_id: str) -> Optional[SegmentVideoResponse]:
        with self._lock:
            return self.jobs.get(job_id)


memory_store = MemoryStore()
