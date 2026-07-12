"""
MemoryStore — almacén en memoria de jobs completados durante la sesión.

Permite que ``GET /api/v1/jobs/{job_id}`` recupere el resultado de una
inferencia ya ejecutada. Es deliberadamente simple (dict protegido por Lock):
el escenario del TIC es local y de usuario único, y los resultados se pierden
al reiniciar el middleware.
"""
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, Optional

from app.schemas.jobs import SegmentVideoResponse


@dataclass
class MemoryStore:
    jobs: Dict[str, SegmentVideoResponse] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def save_job(self, job: SegmentVideoResponse) -> None:
        """Guarda (o sobrescribe) el resultado de un job, indexado por job_id."""
        with self._lock:
            self.jobs[job.job_id] = job

    def get_job(self, job_id: str) -> Optional[SegmentVideoResponse]:
        """Devuelve el job almacenado o None si no existe."""
        with self._lock:
            return self.jobs.get(job_id)


# Singleton compartido: usado por JobService para guardar y consultar jobs.
memory_store = MemoryStore()
