"""
Configuración centralizada del middleware (clase ``Settings``).

Todas las rutas, límites y parámetros operativos se leen desde variables de
entorno con prefijo ``MIDDLEWARE_`` (declaradas en docker-compose.yml),
siguiendo la práctica de configurar el comportamiento desde el entorno y no
desde el código (TIC, Fase 1).
"""
from functools import lru_cache
import os

from pydantic import BaseModel, Field


class Settings(BaseModel):
    service_name: str = Field(default="elan-ai-orchestrator")
    service_version: str = Field(default="0.1.0")
    api_v1_prefix: str = Field(default="/api/v1")
    app_host: str = Field(default="127.0.0.1")
    app_port: int = Field(default=8000)
    log_level: str = Field(default="INFO")
    models_store_dir: str | None = Field(default=None)
    bootstrap_manifests_dir: str | None = Field(default=None)
    runtime_profile: str = Field(default="development")
    # Directorio del HOST donde se encuentran los videos.
    # Cuando un contenedor de modelo se inicia automáticamente, esta ruta se
    # monta en solo lectura como /data/videos dentro del contenedor.
    # MIDDLEWARE_VIDEOS_DIR debe ser una ruta absoluta antes de instalar modelos.
    videos_dir: str | None = Field(default=None)
    # Nombre de la red Docker compartida entre el contenedor del middleware y
    # los contenedores de modelo que este crea.  Con la red configurada, el
    # middleware se comunica con cada backend por nombre de contenedor (DNS
    # interno de Docker), sin mapear puertos al host.  Debe coincidir con la
    # red declarada en docker-compose.yml (name: elan-ai-shared).
    docker_network: str | None = Field(default=None)
    # Número máximo de jobs de inferencia que pueden ejecutarse simultáneamente.
    # Actúa como mecanismo de control de VRAM: limitar la concurrencia evita
    # que múltiples backends Docker carguen pesos en GPU al mismo tiempo,
    # previniendo errores de out-of-memory (OOM) bajo carga concurrente.
    # Valor por defecto: 1 (un solo backend activo a la vez).
    # Configurable con la variable de entorno MIDDLEWARE_MAX_CONCURRENT_JOBS.
    max_concurrent_jobs: int = Field(default=1, gt=0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Construye (una sola vez) el objeto Settings desde las variables de entorno."""
    return Settings(
        service_name=os.getenv("MIDDLEWARE_SERVICE_NAME", "elan-ai-orchestrator"),
        service_version=os.getenv("MIDDLEWARE_SERVICE_VERSION", "0.1.0"),
        api_v1_prefix=os.getenv("MIDDLEWARE_API_V1_PREFIX", "/api/v1"),
        app_host=os.getenv("MIDDLEWARE_HOST", "127.0.0.1"),
        app_port=int(os.getenv("MIDDLEWARE_PORT", "8000")),
        log_level=os.getenv("MIDDLEWARE_LOG_LEVEL", "INFO").upper(),
        models_store_dir=os.getenv("MIDDLEWARE_MODELS_STORE_DIR"),
        bootstrap_manifests_dir=os.getenv("MIDDLEWARE_BOOTSTRAP_MANIFESTS_DIR"),
        runtime_profile=os.getenv("MIDDLEWARE_RUNTIME_PROFILE", "development").lower(),
        videos_dir=os.getenv("MIDDLEWARE_VIDEOS_DIR"),
        docker_network=os.getenv("MIDDLEWARE_DOCKER_NETWORK") or None,
        max_concurrent_jobs=int(os.getenv("MIDDLEWARE_MAX_CONCURRENT_JOBS", "1")),
    )
