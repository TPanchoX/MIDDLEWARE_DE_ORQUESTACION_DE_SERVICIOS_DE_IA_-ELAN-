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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        service_name=os.getenv("MIDDLEWARE_SERVICE_NAME", "elan-ai-orchestrator"),
        service_version=os.getenv("MIDDLEWARE_SERVICE_VERSION", "0.1.0"),
        api_v1_prefix=os.getenv("MIDDLEWARE_API_V1_PREFIX", "/api/v1"),
        app_host=os.getenv("MIDDLEWARE_HOST", "127.0.0.1"),
        app_port=int(os.getenv("MIDDLEWARE_PORT", "8000")),
        log_level=os.getenv("MIDDLEWARE_LOG_LEVEL", "INFO").upper(),
    )
