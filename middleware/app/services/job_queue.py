"""
Cola FIFO de jobs con límite de concurrencia configurable.

Justificación de tesis (objetivo específico 2):
    "...haciendo uso de algoritmos de gestión de colas y asignación dinámica
    de memoria VRAM para asegurar la estabilidad del sistema durante la
    inferencia de modelos pesados."

La cola garantiza dos propiedades fundamentales:

1. Orden FIFO estricto dentro del nivel de concurrencia configurado.
   Los jobs se despachan en el mismo orden en que llegan.

2. Control de concurrencia como mecanismo de asignación de VRAM.
   Cada contenedor de modelo Docker carga sus pesos en GPU al iniciar la
   inferencia.  Limitar a N jobs simultáneos equivale a limitar a N modelos
   cargados en VRAM al mismo tiempo, previniendo errores de out-of-memory
   (OOM) bajo carga concurrente.  Con el valor por defecto (N=1) solo un
   backend puede inferir a la vez, garantizando estabilidad máxima.

Integración con FastAPI / uvicorn:
    El método submit() bloquea el hilo HTTP que lo llama (no el event loop
    de asyncio).  Uvicorn usa un thread pool para endpoints síncronos, por
    lo que bloquear ese hilo no afecta la capacidad de procesar otras
    requests en paralelo.  El contrato síncrono de POST /api/v1/jobs/
    segment-video se conserva sin modificar ELAN.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class JobQueue:
    """Cola FIFO con límite de concurrencia configurable.

    Cada llamada a :meth:`submit` bloquea el hilo que la invoca hasta que
    haya un slot disponible y el job termine.  El orden de despacho es
    estrictamente FIFO dentro de la cola de espera.

    Parameters
    ----------
    max_concurrent:
        Número máximo de jobs que pueden ejecutarse simultáneamente.
        Valor por defecto: 1 (un solo backend activo a la vez).
    """

    def __init__(self, max_concurrent: int = 1) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent debe ser al menos 1.")
        self._max_concurrent = max_concurrent
        self._active_count: int = 0
        # Deque de (job_id, threading.Event) — garantiza orden FIFO
        self._waiting: deque[tuple[str, threading.Event]] = deque()
        self._active_ids: set[str] = set()
        self._lock = threading.Lock()

        logger.info(
            "JobQueue inicializada con max_concurrent=%d.",
            self._max_concurrent,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def submit(self, job_id: str, fn: Callable[[], T]) -> T:
        """Ejecuta *fn* en cuanto haya un slot disponible.

        Si todos los slots están ocupados, el hilo llamante queda bloqueado
        hasta que el job más antiguo de la cola sea despachado (orden FIFO).
        Cualquier excepción lanzada por *fn* se propaga normalmente al
        llamante.

        Parameters
        ----------
        job_id:
            Identificador único del job (usado para logging y trazabilidad).
        fn:
            Función sin argumentos que ejecuta la inferencia.

        Returns
        -------
        T
            Valor de retorno de *fn*.
        """
        event = threading.Event()

        with self._lock:
            if self._active_count < self._max_concurrent:
                # Hay slot disponible: despachar inmediatamente.
                self._active_count += 1
                self._active_ids.add(job_id)
                event.set()
                logger.debug(
                    "Job '%s' despachado de inmediato (activos=%d/%d).",
                    job_id,
                    self._active_count,
                    self._max_concurrent,
                )
            else:
                # Sin slot: encolar y esperar.
                self._waiting.append((job_id, event))
                logger.info(
                    "Job '%s' encolado (posición=%d, activos=%d/%d).",
                    job_id,
                    len(self._waiting),
                    self._active_count,
                    self._max_concurrent,
                )

        # Bloquea hasta recibir señal (para jobs en cola) o pasa directo
        # (para jobs despachados inmediatamente, event ya está seteado).
        event.wait()

        try:
            return fn()
        finally:
            self._release(job_id)

    # ------------------------------------------------------------------
    # Observabilidad (usada por MetricsService y GET /api/v1/metrics)
    # ------------------------------------------------------------------

    @property
    def queued_count(self) -> int:
        """Número de jobs esperando un slot de concurrencia."""
        with self._lock:
            return len(self._waiting)

    @property
    def active_count(self) -> int:
        """Número de jobs en ejecución activa."""
        with self._lock:
            return self._active_count

    @property
    def max_concurrent(self) -> int:
        """Límite de concurrencia configurado."""
        return self._max_concurrent

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _release(self, job_id: str) -> None:
        """Libera el slot y despierta el siguiente job en cola (FIFO)."""
        with self._lock:
            self._active_ids.discard(job_id)
            self._active_count -= 1

            if self._waiting:
                next_id, next_event = self._waiting.popleft()
                self._active_count += 1
                self._active_ids.add(next_id)
                logger.info(
                    "Job '%s' finalizado. Despachando siguiente job '%s' "
                    "(activos=%d/%d, en_cola=%d).",
                    job_id,
                    next_id,
                    self._active_count,
                    self._max_concurrent,
                    len(self._waiting),
                )
                next_event.set()
            else:
                logger.debug(
                    "Job '%s' finalizado. Cola vacía (activos=%d/%d).",
                    job_id,
                    self._active_count,
                    self._max_concurrent,
                )


def _create_queue() -> JobQueue:
    """Crea la instancia singleton usando la configuración del entorno."""
    from app.core.config import get_settings

    settings = get_settings()
    return JobQueue(max_concurrent=settings.max_concurrent_jobs)


# Singleton compartido por job_service y routes_metrics.
job_queue = _create_queue()
