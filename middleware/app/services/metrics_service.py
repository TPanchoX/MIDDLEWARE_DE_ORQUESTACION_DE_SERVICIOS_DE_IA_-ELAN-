"""
Servicio de métricas en memoria para observabilidad del middleware.

Justificación de tesis (objetivo específico 3):
    "Validar el desempeño técnico del middleware mediante pruebas de carga,
    midiendo latencia de comunicación y la correcta recuperación de errores
    ante fallos de los modelos."

Este módulo provee los contadores necesarios para demostrar ese objetivo:
    - Latencia promedio y última ejecución (average_exec_ms, last_exec_ms).
    - Desglose de fallos por tipo de error (error_counts).
    - Diferenciación explícita de TIMEOUT vs FAILED para validar recuperación
      de errores ante modelos que no responden en tiempo.

Los datos se mantienen exclusivamente en memoria.  Se reinician cuando el
middleware se reinicia.  No se requiere base de datos.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MetricsService:
    """Contadores thread-safe del ciclo de vida de jobs.

    Todos los métodos públicos son seguros para llamar desde múltiples hilos
    (el thread pool de uvicorn + el hilo del job en ejecución).
    """

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ── Contadores de estado ──────────────────────────────────────────────
    total_jobs: int = 0
    """Total de jobs recibidos desde el inicio del middleware."""

    completed_jobs: int = 0
    """Jobs que finalizaron en estado COMPLETED."""

    failed_jobs: int = 0
    """Jobs que finalizaron en estado FAILED."""

    timeout_jobs: int = 0
    """Jobs que finalizaron en estado TIMEOUT (excedieron timeout_sec)."""

    # ── Timing ───────────────────────────────────────────────────────────
    _exec_times_ms: list[int] = field(default_factory=list, repr=False)
    """Tiempos de ejecución (wall-clock) de todos los jobs completados."""

    # ── Desglose de errores ───────────────────────────────────────────────
    error_counts: dict[str, int] = field(default_factory=dict)
    """Cantidad de ocurrencias de cada error_code desde el inicio."""

    # ------------------------------------------------------------------
    # Registro de eventos (llamados desde job_service)
    # ------------------------------------------------------------------

    def record_started(self) -> None:
        """Registra que un nuevo job fue recibido."""
        with self._lock:
            self.total_jobs += 1

    def record_completed(self, exec_ms: int) -> None:
        """Registra que un job terminó exitosamente.

        Parameters
        ----------
        exec_ms:
            Tiempo total de ejecución del job en milisegundos
            (desde RECEIVED hasta COMPLETED).
        """
        with self._lock:
            self.completed_jobs += 1
            self._exec_times_ms.append(exec_ms)

    def record_failed(self, error_code: str) -> None:
        """Registra que un job terminó en estado FAILED.

        Parameters
        ----------
        error_code:
            Código de error estructurado (ej: ``DOCKER_INFERENCE_ERROR``).
        """
        with self._lock:
            self.failed_jobs += 1
            self.error_counts[error_code] = (
                self.error_counts.get(error_code, 0) + 1
            )

    def record_timeout(self, error_code: str) -> None:
        """Registra que un job terminó en estado TIMEOUT.

        Se distingue de FAILED porque permite analizar específicamente
        los casos donde el modelo no respondió en el tiempo configurado,
        separándolos de errores funcionales del backend.

        Parameters
        ----------
        error_code:
            Código de error (normalmente ``DOCKER_TIMEOUT``).
        """
        with self._lock:
            self.timeout_jobs += 1
            self.error_counts[error_code] = (
                self.error_counts.get(error_code, 0) + 1
            )

    # ------------------------------------------------------------------
    # Snapshot (llamado desde GET /api/v1/metrics)
    # ------------------------------------------------------------------

    def snapshot(self, *, active_jobs: int, queued_jobs: int) -> dict[str, Any]:
        """Devuelve un snapshot atómico de todas las métricas.

        Parameters
        ----------
        active_jobs:
            Jobs actualmente en ejecución (obtenido de JobQueue.active_count).
        queued_jobs:
            Jobs esperando un slot (obtenido de JobQueue.queued_count).

        Returns
        -------
        dict
            Diccionario compatible con el schema MiddlewareMetrics.
        """
        with self._lock:
            times = list(self._exec_times_ms)

        avg: float | None = (
            round(sum(times) / len(times), 2) if times else None
        )
        last: int | None = times[-1] if times else None

        with self._lock:
            error_counts_copy = dict(self.error_counts)
            return {
                "total_jobs": self.total_jobs,
                "completed_jobs": self.completed_jobs,
                "failed_jobs": self.failed_jobs,
                "timeout_jobs": self.timeout_jobs,
                "active_jobs": active_jobs,
                "queued_jobs": queued_jobs,
                "average_exec_ms": avg,
                "last_exec_ms": last,
                "error_counts": error_counts_copy,
            }


# Singleton compartido por job_service y routes_metrics.
metrics_service = MetricsService()
