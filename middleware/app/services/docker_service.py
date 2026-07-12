"""
DockerService — wrapper del SDK de Docker para Python usado en cada inferencia.

Responsabilidades (TIC, Fase 3):
- ``ensure_container()``: garantiza que el contenedor del modelo exista y esté
  corriendo (lo reutiliza, lo reinicia si está detenido o lo crea desde la
  imagen), unido a la red compartida ``elan-ai-shared``.
- ``wait_for_health()``: polling sobre ``GET /health`` del backend cada 250 ms
  hasta el timeout configurado.
- ``post_json()``: envía la solicitud ``POST /infer`` al backend y distingue
  timeout (``DOCKER_TIMEOUT``/504) de error funcional
  (``DOCKER_INFERENCE_ERROR``/502).

La jerarquía de excepciones define el mapeo error → código HTTP que consume
el manejador global de ``main.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import socket
from time import monotonic, perf_counter, sleep
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import docker
except ImportError:  # pragma: no cover - ocurre solo si falta la dependencia.
    docker = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class DockerServiceError(Exception):
    error_code = "DOCKER_INFERENCE_ERROR"
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class DockerNotAvailableError(DockerServiceError):
    error_code = "DOCKER_NOT_AVAILABLE"
    status_code = 503


class DockerImageNotFoundError(DockerServiceError):
    error_code = "DOCKER_IMAGE_NOT_FOUND"
    status_code = 404


class DockerContainerStartError(DockerServiceError):
    error_code = "DOCKER_CONTAINER_START_ERROR"
    status_code = 502


class DockerContainerHealthcheckFailedError(DockerServiceError):
    error_code = "DOCKER_CONTAINER_HEALTHCHECK_FAILED"
    status_code = 502


class DockerInferenceError(DockerServiceError):
    error_code = "DOCKER_INFERENCE_ERROR"
    status_code = 502


class DockerTimeoutError(DockerServiceError):
    error_code = "DOCKER_TIMEOUT"
    status_code = 504


class UnsupportedDockerContractError(DockerServiceError):
    error_code = "UNSUPPORTED_DOCKER_CONTRACT"
    status_code = 422


@dataclass(frozen=True)
class DockerContainerHandle:
    container_id: str
    base_url: str
    container_start_ms: int


@dataclass(frozen=True)
class DockerHttpResult:
    payload: dict[str, Any]
    elapsed_ms: int


class DockerService:
    def __init__(self) -> None:
        self._client: Any | None = None

    def ensure_container(
        self,
        *,
        image: str,
        model_id: str,
        model_version: str,
        internal_port: int,
        host_port: int | None = None,
        container_name: str | None = None,
        environment: dict[str, str] | None = None,
        volumes: dict[str, Any] | None = None,
        network: str | None = None,
    ) -> DockerContainerHandle:
        """Inicia (o reutiliza) el contenedor del modelo para la imagen dada.

        Ciclo de vida antes de inferir (TIC, Fase 3): si el contenedor ya
        está corriendo se reutiliza (``container_start_ms = 0``, warm start);
        si existe pero está detenido se reinicia; si no existe pero la imagen
        sí, se crea uno nuevo con nombre determinístico
        ``elan-ai-model-{model_id}-{version}``, red y volúmenes. Si falta la
        imagen se lanza ``DockerImageNotFoundError`` (404 → reinstalar).

        Parameters
        ----------
        network:
            Si se proporciona, el contenedor se une a esa red Docker y la
            ``base_url`` devuelta usa el nombre del contenedor como hostname
            (``http://<nombre>:<puerto_interno>``): comunicación
            contenedor-a-contenedor sin mapear puertos al host, requerida
            cuando el middleware corre dentro de Docker. Si es *None*, el
            contenedor publica un puerto del host y la ``base_url`` usa
            ``127.0.0.1:<host_port>`` (modo desarrollo fuera de Docker).
        """
        client = self._available_client()
        self._ensure_image_exists(client=client, image=image)

        name = container_name or self._container_name(model_id=model_id, model_version=model_version)
        started_at = perf_counter()
        try:
            container = self._get_container(client=client, name=name)
            self._assert_container_image(container=container, expected_image=image, name=name)
            container_start_ms = 0
            if self._container_status(container) != "running":
                container.start()
                container.reload()
                container_start_ms = self._elapsed_ms(started_at)
            # Reconectar a la red compartida si hace falta (cubre contenedores
            # creados antes de que la red estuviera configurada).
            if network:
                self._connect_to_network(client=client, container=container, network=network)
        except self._not_found_error():
            try:
                run_kwargs: dict[str, Any] = dict(
                    image=image,
                    name=name,
                    detach=True,
                    environment=environment or None,
                    volumes=volumes or None,
                    labels={
                        "elan-ai-orchestrator": "true",
                        "elan-ai-model-id": model_id,
                        "elan-ai-model-version": model_version,
                    },
                )
                if network:
                    # Modo contenedor-a-contenedor: se une a la red compartida;
                    # no se necesita mapear puertos al host.
                    run_kwargs["network"] = network
                else:
                    # Modo alternativo por puerto del host (middleware fuera de Docker).
                    run_kwargs["ports"] = {f"{internal_port}/tcp": host_port}

                container = client.containers.run(**run_kwargs)
                container.reload()
                container_start_ms = self._elapsed_ms(started_at)
            except Exception as exc:
                raise DockerContainerStartError(
                    f"Could not start Docker container for image '{image}': {exc}"
                ) from exc
        except DockerServiceError:
            raise
        except Exception as exc:
            raise DockerContainerStartError(
                f"Could not ensure Docker container for image '{image}': {exc}"
            ) from exc

        if network:
            # Accesible desde el contenedor del middleware vía DNS interno de Docker.
            base_url = f"http://{name}:{internal_port}"
        else:
            base_url = self._container_base_url(container=container, internal_port=internal_port)

        return DockerContainerHandle(
            container_id=str(container.id),
            base_url=base_url,
            container_start_ms=container_start_ms,
        )

    def wait_for_health(self, *, base_url: str, health_path: str, timeout_sec: int) -> int:
        """Espera activa a que GET /health del backend responda 2xx.

        Reintenta cada 250 ms hasta ``timeout_sec`` (30 s por defecto durante
        la inferencia, según ``container.startup_timeout_sec``). Devuelve los
        milisegundos transcurridos, que se reportan como ``healthcheck_ms``
        en la trazabilidad del job.
        """
        started_at = perf_counter()
        deadline = monotonic() + timeout_sec
        url = self._join_url(base_url=base_url, path=health_path)
        last_error = "health endpoint did not respond"

        while monotonic() < deadline:
            remaining = max(0.1, deadline - monotonic())
            try:
                request = Request(url, method="GET")
                with urlopen(request, timeout=min(2.0, remaining)) as response:
                    if 200 <= response.status < 300:
                        return self._elapsed_ms(started_at)
                    last_error = f"health endpoint returned HTTP {response.status}"
            except (HTTPError, URLError, TimeoutError, socket.timeout) as exc:
                last_error = str(exc)
            sleep(0.25)

        raise DockerContainerHealthcheckFailedError(
            f"Docker model service health check failed at '{url}' after {timeout_sec}s: {last_error}"
        )

    def post_json(self, *, base_url: str, path: str, payload: dict[str, Any], timeout_sec: int) -> DockerHttpResult:
        """Envía POST /infer al backend y clasifica el resultado.

        - Timeout del socket → ``DockerTimeoutError`` (504, estado TIMEOUT).
        - HTTP 4xx/5xx del backend → ``DockerInferenceError`` (502) con el
          body del backend como detalle.
        - Respuesta no-JSON → ``DockerInferenceError``.
        El ``timeout_sec`` proviene de ``execution.timeout_sec`` del request
        (300 s por defecto).
        """
        started_at = perf_counter()
        url = self._join_url(base_url=base_url, path=path)
        body = json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=timeout_sec) as response:
                response_body = response.read()
        except (TimeoutError, socket.timeout) as exc:
            raise DockerTimeoutError(f"Docker inference timed out after {timeout_sec}s.") from exc
        except HTTPError as exc:
            detail = self._read_error_body(exc)
            raise DockerInferenceError(
                f"Docker inference endpoint returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            if isinstance(exc.reason, socket.timeout):
                raise DockerTimeoutError(f"Docker inference timed out after {timeout_sec}s.") from exc
            raise DockerInferenceError(f"Docker inference endpoint could not be reached: {exc}") from exc

        try:
            decoded = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DockerInferenceError("Docker inference response must be valid UTF-8 JSON.") from exc
        if not isinstance(decoded, dict):
            raise DockerInferenceError("Docker inference response must be a JSON object.")

        return DockerHttpResult(payload=decoded, elapsed_ms=self._elapsed_ms(started_at))

    def _available_client(self) -> Any:
        """Devuelve el cliente del SDK de Docker verificando que el daemon responda (ping)."""
        if docker is None:
            raise DockerNotAvailableError(
                "Docker SDK for Python is not installed. Install requirements.txt before using DockerRunner."
            )
        try:
            if self._client is None:
                self._client = docker.from_env()
            self._client.ping()
            return self._client
        except Exception as exc:
            self._client = None
            raise DockerNotAvailableError(
                "Docker is not available. Verify Docker Desktop/daemon is installed and running."
            ) from exc

    def _ensure_image_exists(self, *, client: Any, image: str) -> None:
        """Verifica que la imagen exista localmente; si falta responde 404 (reinstalar modelo)."""
        try:
            client.images.get(image)
        except self._image_not_found_error() as exc:
            raise DockerImageNotFoundError(f"Docker image '{image}' was not found locally.") from exc
        except Exception as exc:
            raise DockerNotAvailableError(f"Docker image lookup failed: {exc}") from exc

    def _get_container(self, *, client: Any, name: str) -> Any:
        return client.containers.get(name)

    def _assert_container_image(self, *, container: Any, expected_image: str, name: str) -> None:
        tags = getattr(container.image, "tags", []) or []
        if expected_image not in tags:
            raise DockerContainerStartError(
                f"Existing container '{name}' does not use expected image '{expected_image}'."
            )

    def _container_base_url(self, *, container: Any, internal_port: int) -> str:
        try:
            container.reload()
            ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            bindings = ports.get(f"{internal_port}/tcp")
            if not bindings:
                raise KeyError(f"{internal_port}/tcp")
            host_port = bindings[0]["HostPort"]
        except Exception as exc:
            raise DockerContainerStartError(
                f"Docker container does not expose internal port {internal_port} to the host."
            ) from exc
        return f"http://127.0.0.1:{host_port}"

    def _connect_to_network(self, *, client: Any, container: Any, network: str) -> None:
        """Conecta *container* a *network* si aún no está conectado (falla solo con warning)."""
        try:
            net = client.networks.get(network)
            net.reload()
            connected_ids = {c.id for c in net.containers}
            if container.id not in connected_ids:
                net.connect(container)
                logger.info(
                    "Connected container '%s' to network '%s'.",
                    container.name, network,
                )
        except Exception as exc:
            logger.warning(
                "Could not connect container '%s' to network '%s': %s",
                container.name, network, exc,
            )

    def _not_found_error(self) -> type[Exception]:
        return docker.errors.NotFound if docker is not None else Exception

    def _image_not_found_error(self) -> type[Exception]:
        return docker.errors.ImageNotFound if docker is not None else Exception

    @staticmethod
    def _container_status(container: Any) -> str:
        container.reload()
        return str(getattr(container, "status", "")).lower()

    @staticmethod
    def _container_name(*, model_id: str, model_version: str) -> str:
        """Nombre determinístico ``elan-ai-model-{id}-{versión}`` saneado para Docker."""
        raw_name = f"elan-ai-model-{model_id}-{model_version}".lower()
        name = re.sub(r"[^a-z0-9_.-]+", "-", raw_name).strip("-")
        return name[:120] or "elan-ai-model"

    @staticmethod
    def _join_url(*, base_url: str, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{base_url.rstrip('/')}{normalized_path}"

    @staticmethod
    def _read_error_body(exc: HTTPError) -> str:
        try:
            body = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""
        return body or exc.reason or "no response body"

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))


docker_service = DockerService()
