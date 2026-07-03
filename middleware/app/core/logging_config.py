"""
Logging estructurado del middleware.

Cada mensaje incluye marca de tiempo, severidad, módulo de origen y
descripción, lo que permite seguir las transiciones de estado de un job
(RECEIVED → ... → COMPLETED/FAILED/TIMEOUT) y diagnosticar fallos.
La verbosidad se controla con MIDDLEWARE_LOG_LEVEL (TIC, Fase 1).
"""
import logging

from app.core.config import get_settings


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging() -> None:
    settings = get_settings()
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format=LOG_FORMAT,
        force=True,
    )
