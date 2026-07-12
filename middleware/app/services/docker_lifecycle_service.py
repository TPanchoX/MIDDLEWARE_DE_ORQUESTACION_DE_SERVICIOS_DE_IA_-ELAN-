"""
DockerLifecycleService — construcción y arranque automáticos de backends.

Cuando un paquete de modelo se instala vía POST /models/install y su manifest
declara el artefacto ``dockerfile``, este servicio (TIC, Fase 2):

  1. Ejecuta ``docker build`` usando el paquete extraído como contexto de
     construcción (Dockerfile en backend/Dockerfile, contexto = raíz del
     paquete, lo que permite copiar weights/, vocab/ y config/).
  2. Arranca el contenedor resultante mediante DockerService.
  3. Espera a que el health check del backend pase (hasta
     ``backend_config.startup_timeout_sec``; 180 s en el modelo de
     referencia porque la primera carga de pesos es lenta, 120 s si se omite).

Si cualquier paso falla, ModelRegistryService ejecuta el rollback de la
instalación y responde 400 MODEL_PACKAGE_INVALID.
"""

from __future__ import annotations

import json
import logging
import socket
from pathlib import Path
from time import monotonic, sleep
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import docker as docker_sdk
except ImportError:  # pragma: no cover
    docker_sdk = None  # type: ignore[assignment]

from app.core.config import get_settings
from app.services.docker_service import DockerService, docker_service


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepciones (error_code + status_code que consume el manejador de main.py)
# ---------------------------------------------------------------------------

class DockerLifecycleError(Exception):
    error_code = "DOCKER_LIFECYCLE_ERROR"
    status_code = 500

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class DockerBuildError(DockerLifecycleError):
    error_code = "DOCKER_BUILD_ERROR"


class DockerStartError(DockerLifecycleError):
    error_code = "DOCKER_START_ERROR"


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------

class DockerLifecycleService:
    """Construye y arranca los contenedores Docker de los paquetes de modelo recién instalados."""

    DOCKERFILE_REL = "backend/Dockerfile"

    def __init__(self, service: DockerService | None = None) -> None:
        self._service = service or docker_service
        self._client = None  # cliente del SDK de Docker (se crea al primer uso)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def build_and_start(
        self,
        install_path: Path,
        *,
        model_id: str,
        model_version: str,
        backend_config: dict,
        videos_dir: str | None = None,
    ) -> None:
        """
        Construye la imagen Docker desde *install_path*/backend/Dockerfile
        (contexto de build = raíz de *install_path*) y la arranca como un
        contenedor accesible desde el middleware.

        Parameters
        ----------
        install_path:
            Ruta absoluta del directorio del paquete de modelo extraído.
        model_id / model_version:
            Usados para nombrar el contenedor de forma determinística
            (``elan-ai-model-{model_id}-{version}``).
        backend_config:
            Dict del campo ``backend_config`` del manifest. Claves
            reconocidas: docker_image_name, docker_image_tag, container_port,
            health_path, infer_path, startup_timeout_sec.
        videos_dir:
            Si se proporciona, se monta en solo lectura como ``/data/videos``
            dentro del contenedor para que el backend lea los videos.
        """
        image_name = str(backend_config.get("docker_image_name") or model_id).lower().replace("_", "-")
        image_tag = str(backend_config.get("docker_image_tag") or model_version)
        full_image = f"{image_name}:{image_tag}"
        container_port = int(backend_config.get("container_port") or 8080)
        startup_timeout = int(backend_config.get("startup_timeout_sec") or 120)
        health_path = str(backend_config.get("health_path") or "/health")
        if not health_path.startswith("/"):
            health_path = f"/{health_path}"

        # 1. Build ---------------------------------------------------------
        logger.info(
            "Building Docker image '%s' — context: '%s', dockerfile: '%s'.",
            full_image, install_path, self.DOCKERFILE_REL,
        )
        self._build_image(install_path=install_path, image_tag=full_image)
        logger.info("Docker image '%s' built successfully.", full_image)

        # 2. Start ---------------------------------------------------------
        volumes = self._build_volumes(videos_dir=videos_dir)
        docker_network = get_settings().docker_network
        logger.info(
            "Starting Docker container for model '%s' version '%s' (image '%s')%s.",
            model_id, model_version, full_image,
            f" on network '{docker_network}'" if docker_network else " (host-port mode)",
        )
        try:
            handle = self._service.ensure_container(
                image=full_image,
                model_id=model_id,
                model_version=model_version,
                internal_port=container_port,
                volumes=volumes,
                network=docker_network,
            )
        except Exception as exc:
            raise DockerStartError(
                f"Could not start container for image '{full_image}': {exc}"
            ) from exc

        # 3. Health check --------------------------------------------------
        logger.info(
            "Waiting for container health check at %s%s (timeout=%ds).",
            handle.base_url, health_path, startup_timeout,
        )
        try:
            self._wait_for_healthy(
                base_url=handle.base_url,
                health_path=health_path,
                startup_timeout=startup_timeout,
                full_image=full_image,
            )
        except DockerStartError:
            raise
        except Exception as exc:
            raise DockerStartError(
                f"Container for image '{full_image}' did not become healthy within "
                f"{startup_timeout}s: {exc}"
            ) from exc

        logger.info(
            "Container for model '%s' version '%s' is healthy at %s.",
            model_id, model_version, handle.base_url,
        )

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _wait_for_healthy(
        self,
        *,
        base_url: str,
        health_path: str,
        startup_timeout: int,
        full_image: str,
    ) -> None:
        """
        Espera de salud en dos fases que produce errores accionables de inmediato.

        Fase 1 — esperar a que uvicorn enlace el puerto (hasta 30 s).
            Reintenta ante ConnectionRefused / URLError.

        Fase 2 — cuando el puerto ya responde:
            • HTTP 200 → éxito.
            • HTTP 5xx → leer el body, extraer el mensaje de error del propio
              backend (campo ``detail``) y lanzar DockerStartError de
              inmediato, sin agotar el startup_timeout.
            • HTTP 4xx → lanzar de inmediato (error de configuración).
        """
        normalized_path = health_path if health_path.startswith("/") else f"/{health_path}"
        url = f"{base_url.rstrip('/')}{normalized_path}"

        # ── Fase 1: esperar a que el puerto acepte conexiones ─────────────────
        BIND_TIMEOUT = min(30, startup_timeout)
        bind_deadline = monotonic() + BIND_TIMEOUT
        server_up = False
        first_http_exc: HTTPError | None = None

        while monotonic() < bind_deadline:
            try:
                with urlopen(Request(url, method="GET"), timeout=2.0) as resp:
                    if 200 <= resp.status < 300:
                        logger.info("Container '%s' is healthy.", full_image)
                        return  # ya está sano durante la fase 1 — listo
                    # Respuesta no-2xx pero hubo conexión — pasar a fase 2
                    server_up = True
                    break
            except HTTPError as exc:
                # El servidor respondió 4xx/5xx — el puerto está abierto
                server_up = True
                first_http_exc = exc
                break
            except (URLError, OSError, socket.timeout, ConnectionRefusedError):
                sleep(0.5)

        if not server_up:
            # El puerto nunca aceptó conexiones en la ventana de arranque →
            # usar la espera estándar durante el tiempo restante.
            remaining = max(10, startup_timeout - BIND_TIMEOUT)
            self._service.wait_for_health(
                base_url=base_url,
                health_path=health_path,
                timeout_sec=remaining,
            )
            return

        # ── Fase 2: el servidor responde — decidir según el estado HTTP ──────
        # Si ya hay un HTTPError capturado en la fase 1, usarlo directamente.
        if first_http_exc is not None:
            self._raise_from_http_error(first_http_exc, full_image)

        # Si no, se recibió un estado no-2xx vía context manager (raro para 5xx
        # con urllib, pero se maneja de forma defensiva).
        #
        # Esperar hasta startup_timeout a que el backend esté sano; cubre el
        # caso en que el modelo todavía está cargando sus pesos.
        elapsed_bind = BIND_TIMEOUT
        remaining_timeout = max(10, startup_timeout - elapsed_bind)
        deadline = monotonic() + remaining_timeout
        last_error = "no response received"

        while monotonic() < deadline:
            remaining = max(0.1, deadline - monotonic())
            try:
                with urlopen(Request(url, method="GET"), timeout=min(2.0, remaining)) as resp:
                    if 200 <= resp.status < 300:
                        logger.info("Container '%s' is healthy.", full_image)
                        return
                    last_error = f"HTTP {resp.status}"
            except HTTPError as exc:
                # Fallar de inmediato ante cualquier error HTTP — el backend está
                # avisando que algo anda mal (p. ej. pesos faltantes).
                self._raise_from_http_error(exc, full_image)
            except (URLError, OSError, socket.timeout, ConnectionRefusedError) as exc:
                last_error = str(exc)
            sleep(0.25)

        raise DockerStartError(
            f"Container for image '{full_image}' did not become healthy within "
            f"{startup_timeout}s. Last status: {last_error}"
        )

    @staticmethod
    def _raise_from_http_error(exc: HTTPError, full_image: str) -> None:
        """Lee el body del error HTTP y lanza DockerStartError con un mensaje claro."""
        try:
            body_bytes = exc.read()
            body = body_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""

        # Intentar extraer el campo 'detail' del body JSON (convención de FastAPI).
        detail: str = body
        if body:
            try:
                payload = json.loads(body)
                if isinstance(payload, dict):
                    detail = str(payload.get("detail", body))
            except Exception:
                pass

        raise DockerStartError(
            f"Container for image '{full_image}' is running but returned HTTP {exc.code}. "
            f"Backend error: {detail or exc.reason}"
        )

    def _build_image(self, install_path: Path, image_tag: str) -> None:
        """Ejecuta ``docker build`` con el paquete extraído como contexto de construcción."""
        client = self._available_client()
        dockerfile_abs = install_path / self.DOCKERFILE_REL
        if not dockerfile_abs.exists():
            raise DockerBuildError(
                f"Dockerfile not found at '{dockerfile_abs}'. "
                f"The package must include '{self.DOCKERFILE_REL}'."
            )

        try:
            _image, _logs = client.images.build(
                path=str(install_path),
                dockerfile=self.DOCKERFILE_REL,
                tag=image_tag,
                rm=True,
                forcerm=True,
            )
        except Exception as exc:
            raise DockerBuildError(
                f"Docker build failed for image '{image_tag}': {exc}"
            ) from exc

    def _available_client(self):
        """Devuelve el cliente del SDK de Docker verificando que el daemon responda (ping)."""
        if docker_sdk is None:
            raise DockerBuildError(
                "Docker SDK for Python ('docker') is not installed. "
                "Add 'docker' to middleware requirements.txt."
            )
        try:
            if self._client is None:
                self._client = docker_sdk.from_env()
            self._client.ping()
            return self._client
        except Exception as exc:
            self._client = None
            raise DockerBuildError(
                "Docker daemon is not reachable. "
                "Ensure Docker Desktop / Docker daemon is running."
            ) from exc

    @staticmethod
    def _build_volumes(videos_dir: str | None) -> dict | None:
        if not videos_dir:
            return None
        # Usar la cadena cruda tal cual — NO aplicar resolve() ni convertir a
        # Path de Linux.  MIDDLEWARE_VIDEOS_DIR es una ruta del HOST (puede ser
        # de Windows, p. ej. "C:/Users/…").  Llamar a Path().resolve() dentro
        # del contenedor Linux antepondría el CWD del contenedor (/app) y
        # rompería el parser de bind mounts de Docker.  Docker Desktop recibe
        # la cadena cruda y la traduce correctamente al filesystem de Windows.
        return {videos_dir: {"bind": "/data/videos", "mode": "ro"}}


# Singleton usado por ModelRegistryService
docker_lifecycle_service = DockerLifecycleService()
