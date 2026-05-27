from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.config import get_settings
from app.runners.base_runner import BaseRunner
from app.schemas.inference import InferenceInput, InferenceOutput
from app.schemas.jobs import MediaInfo, TemporalSegment
from app.schemas.metrics import StageMetrics
from app.services.docker_service import (
    DockerService,
    UnsupportedDockerContractError,
    docker_service,
)


class DockerRunner(BaseRunner):
    runner_name = "docker_http"
    device = "container"

    def __init__(self, service: DockerService | None = None) -> None:
        self.service = service or docker_service

    def run(self, request: InferenceInput) -> InferenceOutput:
        config = self._container_config(request.container)
        image = self._docker_image(request, required=not bool(config["service_url"]))

        if config["service_url"]:
            base_url = config["service_url"]
            container_id = self._compose_container_id(config)
            container_start_ms = 0
        else:
            assert image is not None
            settings = get_settings()

            # Merge the global videos-dir volume (if configured) with any
            # volumes declared in the model manifest's container section.
            # The videos dir is mounted read-only at /data/videos so the
            # model backend can access video files by their container path.
            merged_volumes: dict[str, Any] | None = config["volumes"]
            if settings.videos_dir and settings.videos_dir.strip():
                videos_vol: dict[str, Any] = {
                    settings.videos_dir.strip(): {"bind": "/data/videos", "mode": "ro"}
                }
                merged_volumes = {**videos_vol, **(merged_volumes or {})}

            handle = self.service.ensure_container(
                image=image,
                model_id=request.model_id,
                model_version=request.model_version,
                internal_port=config["internal_port"],
                host_port=config["host_port"],
                container_name=config["container_name"],
                environment=config["environment"],
                volumes=merged_volumes,
                # Pass the shared Docker network so container-to-container
                # communication works when the middleware itself runs in Docker.
                network=settings.docker_network,
            )
            base_url = handle.base_url
            container_id = handle.container_id
            container_start_ms = handle.container_start_ms

        healthcheck_ms = self.service.wait_for_health(
            base_url=base_url,
            health_path=config["health_path"],
            timeout_sec=config["startup_timeout_sec"],
        )
        inference_result = self.service.post_json(
            base_url=base_url,
            path=config["infer_path"],
            payload=self._build_payload(request=request),
            timeout_sec=request.timeout_sec,
        )

        metrics = StageMetrics(
            container_start_ms=container_start_ms,
            healthcheck_ms=healthcheck_ms,
            docker_inference_ms=inference_result.elapsed_ms,
            inference_ms=inference_result.elapsed_ms,
            total_ms=container_start_ms + healthcheck_ms + inference_result.elapsed_ms,
        )
        output = self._adapt_response(payload=inference_result.payload, metrics=metrics)
        output.runner_trace.update(
            {
                "docker_image": image,
                "container_id": container_id,
                "container_start_ms": container_start_ms,
                "healthcheck_ms": healthcheck_ms,
                "docker_inference_ms": inference_result.elapsed_ms,
                "docker_mode": "compose_service" if config["service_url"] else "sdk_managed",
            }
        )
        return output

    def _docker_image(self, request: InferenceInput, *, required: bool) -> str | None:
        image = request.artifacts.get("docker_image")
        if image is None or not image.strip():
            if required:
                raise UnsupportedDockerContractError(
                    "Docker model manifest must declare artifacts.docker_image "
                    "when container.service_url is not configured."
                )
            return None
        return image.strip()

    def _container_config(self, raw_config: dict[str, object]) -> dict[str, Any]:
        internal_port = self._positive_int(raw_config.get("internal_port", 8080), "container.internal_port")
        startup_timeout_sec = self._positive_int(
            raw_config.get("startup_timeout_sec", 30),
            "container.startup_timeout_sec",
        )
        host_port = raw_config.get("host_port")
        environment = raw_config.get("environment")
        volumes = raw_config.get("volumes")
        container_name = raw_config.get("name") or raw_config.get("container_name")
        service_url = raw_config.get("service_url") or raw_config.get("base_url")
        compose_service = raw_config.get("compose_service")

        return {
            "internal_port": internal_port,
            "host_port": None if host_port is None else self._positive_int(host_port, "container.host_port"),
            "health_path": self._path(raw_config.get("health_path", "/health"), "container.health_path"),
            "infer_path": self._path(raw_config.get("infer_path", "/infer"), "container.infer_path"),
            "startup_timeout_sec": startup_timeout_sec,
            "environment": self._string_dict(environment, "container.environment"),
            "volumes": self._object_dict(volumes, "container.volumes"),
            "container_name": None if container_name is None else self._non_empty_string(container_name, "container.name"),
            "service_url": None if service_url is None else self._url(service_url, "container.service_url"),
            "compose_service": None if compose_service is None else self._non_empty_string(
                compose_service,
                "container.compose_service",
            ),
        }

    def _build_payload(self, request: InferenceInput) -> dict[str, Any]:
        return {
            "job_id": request.job_id,
            "media": {"path": request.media_path},
            "annotation": request.annotation,
            "parameters": request.parameters,
            "model": {
                "model_id": request.model_id,
                "version": request.model_version,
            },
            "execution": {
                "device_preference": request.device_preference,
                "runner": request.runner_preference,
                "timeout_sec": request.timeout_sec,
            },
        }

    def _adapt_response(self, *, payload: dict[str, Any], metrics: StageMetrics) -> InferenceOutput:
        if "segments" in payload:
            return InferenceOutput(
                output_type=self._segment_output_type(payload),
                segments=self._segments(payload.get("segments")),
                media_info=self._media_info(payload.get("media_info")),
                metrics=metrics,
            )

        raise UnsupportedDockerContractError(
            "Docker /infer response must contain media_info and segments."
        )

    def _segments(self, raw_segments: object) -> list[TemporalSegment]:
        if not isinstance(raw_segments, list):
            raise UnsupportedDockerContractError("Docker segments response must be a list.")
        try:
            return [TemporalSegment.model_validate(segment) for segment in raw_segments]
        except ValidationError as exc:
            raise UnsupportedDockerContractError(f"Docker segments response is invalid: {exc}") from exc

    def _media_info(self, raw_media_info: object) -> MediaInfo:
        if not isinstance(raw_media_info, dict):
            raise UnsupportedDockerContractError("Docker segments response must include media_info.")
        try:
            return MediaInfo.model_validate(raw_media_info)
        except ValidationError as exc:
            raise UnsupportedDockerContractError(f"Docker media_info response is invalid: {exc}") from exc

    @staticmethod
    def _segment_output_type(payload: dict[str, Any]) -> str:
        if payload.get("output_type") == "segments_with_gloss":
            return "segments_with_gloss"
        return "segments"

    @staticmethod
    def _positive_int(value: object, field_name: str) -> int:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise UnsupportedDockerContractError(f"{field_name} must be a positive integer.") from exc
        if parsed <= 0:
            raise UnsupportedDockerContractError(f"{field_name} must be a positive integer.")
        return parsed

    @staticmethod
    def _path(value: object, field_name: str) -> str:
        path = DockerRunner._non_empty_string(value, field_name)
        return path if path.startswith("/") else f"/{path}"

    @staticmethod
    def _url(value: object, field_name: str) -> str:
        url = DockerRunner._non_empty_string(value, field_name).rstrip("/")
        if not (url.startswith("http://") or url.startswith("https://")):
            raise UnsupportedDockerContractError(f"{field_name} must start with http:// or https://.")
        return url

    @staticmethod
    def _compose_container_id(config: dict[str, Any]) -> str | None:
        compose_service = config.get("compose_service")
        if isinstance(compose_service, str) and compose_service:
            return f"compose:{compose_service}"
        service_url = config.get("service_url")
        if isinstance(service_url, str) and service_url:
            return f"service:{service_url}"
        return None

    @staticmethod
    def _non_empty_string(value: object, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise UnsupportedDockerContractError(f"{field_name} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _string_dict(value: object, field_name: str) -> dict[str, str] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise UnsupportedDockerContractError(f"{field_name} must be an object.")
        return {str(key): str(item) for key, item in value.items()}

    @staticmethod
    def _object_dict(value: object, field_name: str) -> dict[str, Any] | None:
        if value is None:
            return None
        if not isinstance(value, dict):
            raise UnsupportedDockerContractError(f"{field_name} must be an object.")
        return dict(value)
