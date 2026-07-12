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
    """Runner que ejecuta inferencias en el contenedor Docker del modelo (TIC, Fase 3).

    Prepara el entorno antes de cada solicitud: asegura que el contenedor
    exista y esté corriendo (``ensure_container``), verifica su disponibilidad
    (polling sobre ``GET /health``), traduce la ruta del video del host al
    punto de montaje interno, construye el payload, invoca ``POST /infer`` y
    adapta la respuesta al contrato interno del middleware. Con esta
    separación, ``JobService`` queda libre de los detalles del SDK de Docker.
    """

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

            # Combina el volumen global de videos (si está configurado) con los
            # volúmenes declarados en la sección container del manifest.
            # El directorio de videos se monta en solo lectura como /data/videos
            # para que el backend pueda abrir los archivos por su ruta interna.
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
                # Red Docker compartida: permite la comunicación contenedor a
                # contenedor cuando el propio middleware corre dentro de Docker.
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
        """Obtiene la imagen Docker declarada en artifacts; obligatoria salvo con service_url."""
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
        """Normaliza y valida la sección ``container`` del manifest (puertos, rutas, volúmenes)."""
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
        """Construye el payload del contrato middleware → backend.

        Traduce ``media.path`` a la ruta visible en el contenedor e incluye
        siempre ``parameters`` (aunque sea ``{}``) para que el backend lea una
        estructura uniforme sin casos especiales.
        """
        settings = get_settings()
        container_media_path = self._translate_media_path(
            request.media_path, settings.videos_dir
        )
        return {
            "job_id": request.job_id,
            "media": {"path": container_media_path},
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

    @staticmethod
    def _translate_media_path(host_path: str, videos_dir: str | None) -> str:
        """Traduce un path del host al path equivalente dentro del contenedor Docker.

        El runner monta ``videos_dir`` (host) como ``/data/videos`` (contenedor,
        solo lectura).  Este método reemplaza el prefijo del host por el punto de
        montaje del contenedor para que el backend pueda abrir el archivo de video.

        Ejemplos
        --------
        host_path  = "C:/Users/user/Desktop/video.mp4"
        videos_dir = "C:/Users/user/Desktop"
        → "/data/videos/video.mp4"

        Si el path no está dentro de ``videos_dir``, se devuelve sin cambios y el
        backend recibirá el path original (puede fallar si no está montado).

        La comparación de prefijos es insensible a mayúsculas para ser robusta
        con paths de Windows.
        """
        if not videos_dir or not videos_dir.strip():
            return host_path

        norm_dir  = videos_dir.strip().rstrip("/\\").replace("\\", "/")
        norm_path = host_path.replace("\\", "/")

        if norm_path.lower().startswith(norm_dir.lower() + "/"):
            relative = norm_path[len(norm_dir):]   # ya incluye la barra inicial
            return "/data/videos" + relative

        return host_path

    def _adapt_response(self, *, payload: dict[str, Any], metrics: StageMetrics) -> InferenceOutput:
        """Valida y adapta la respuesta del backend al contrato del middleware.

        No basta con un HTTP 200: la respuesta debe traer ``media_info`` y
        ``segments`` válidos (validados con Pydantic como ``TemporalSegment``);
        de lo contrario se responde 422 UNSUPPORTED_DOCKER_CONTRACT para que
        una respuesta incompleta nunca llegue a ELAN.
        """
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
