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
    # Directory on the HOST machine where video files are stored.
    # When a model backend Docker container is started automatically,
    # this path is mounted read-only at /data/videos inside the container.
    # Set MIDDLEWARE_VIDEOS_DIR to an absolute path before using auto-install.
    videos_dir: str | None = Field(default=None)
    # Docker network name shared between the middleware container and the model
    # containers it spawns.  When set, model containers are attached to this
    # network and the middleware communicates with them via container-name DNS
    # (no host-port mapping required).  Must match the network declared in
    # docker-compose.yml (name: elan-ai-shared).
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
