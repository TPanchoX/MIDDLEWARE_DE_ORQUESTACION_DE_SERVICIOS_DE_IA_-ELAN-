"""
DockerLifecycleService – auto build & start Docker model backends.

When a model package is installed via POST /models/install and its
manifest declares a ``dockerfile`` artifact, this service:

  1. Runs ``docker build`` using the extracted package as build context
     (Dockerfile at backend/Dockerfile, context = install root).
  2. Starts the resulting container with the DockerService.
  3. Waits for the container health check to pass.

If any step fails the registry service will rollback the installation.
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
# Exceptions
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
# Service
# ---------------------------------------------------------------------------

class DockerLifecycleService:
    """Builds and starts Docker containers for freshly installed model packages."""

    DOCKERFILE_REL = "backend/Dockerfile"

    def __init__(self, service: DockerService | None = None) -> None:
        self._service = service or docker_service
        self._client = None  # lazy Docker SDK client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def build_and_start(
        self,
        install_path: Path,
        *,
        model_id: str,
        model_version: str,
        backend_config: dict,
        videos_dir: Path | None = None,
    ) -> None:
        """
        Build a Docker image from *install_path*/backend/Dockerfile
        (build context = *install_path* root) and start it as a
        container that is accessible from the middleware.

        Parameters
        ----------
        install_path:
            Absolute path to the extracted model package directory.
        model_id / model_version:
            Used to name the container deterministically.
        backend_config:
            Dict from manifest ``backend_config`` field. Recognised keys:
            docker_image_name, docker_image_tag, container_port,
            health_path, infer_path, startup_timeout_sec.
        videos_dir:
            If provided, mounted read-only as ``/data/videos`` in the
            container so the backend can read video files.
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
    # Internal helpers
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
        Two-phase health wait that gives actionable errors immediately.

        Phase 1 — wait for uvicorn to bind (up to 30 s).
            Retries on ConnectionRefused / URLError.

        Phase 2 — once the port responds:
            • HTTP 200 → success.
            • HTTP 5xx → read the body, extract the backend's own error message,
              and raise DockerStartError immediately (no need to wait startup_timeout).
            • HTTP 4xx → raise immediately (configuration error).
        """
        normalized_path = health_path if health_path.startswith("/") else f"/{health_path}"
        url = f"{base_url.rstrip('/')}{normalized_path}"

        # ── Phase 1: wait for the port to accept connections ──────────────────
        BIND_TIMEOUT = min(30, startup_timeout)
        bind_deadline = monotonic() + BIND_TIMEOUT
        server_up = False
        first_http_exc: HTTPError | None = None

        while monotonic() < bind_deadline:
            try:
                with urlopen(Request(url, method="GET"), timeout=2.0) as resp:
                    if 200 <= resp.status < 300:
                        logger.info("Container '%s' is healthy.", full_image)
                        return  # already healthy during phase 1 — done
                    # Non-2xx but connection was made — go to phase 2
                    server_up = True
                    break
            except HTTPError as exc:
                # Server responded with 4xx/5xx — port is open
                server_up = True
                first_http_exc = exc
                break
            except (URLError, OSError, socket.timeout, ConnectionRefusedError):
                sleep(0.5)

        if not server_up:
            # Port never accepted connections in the bind window →
            # fall back to the standard wait for the remaining time.
            remaining = max(10, startup_timeout - BIND_TIMEOUT)
            self._service.wait_for_health(
                base_url=base_url,
                health_path=health_path,
                timeout_sec=remaining,
            )
            return

        # ── Phase 2: server is up — decide based on the HTTP status ──────────
        # If we already have an HTTPError from phase 1, use it directly.
        if first_http_exc is not None:
            self._raise_from_http_error(first_http_exc, full_image)

        # Otherwise we got a non-2xx status via the context manager (shouldn't
        # normally happen for 5xx with urllib, but handle defensively).
        #
        # Wait up to startup_timeout for the backend to become healthy.
        # This covers the case where the model is still loading weights.
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
                # Fail immediately for any HTTP error — the backend is telling us
                # something is wrong (e.g. missing weights).
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
        """Read the HTTP error body and raise DockerStartError with a clear message."""
        try:
            body_bytes = exc.read()
            body = body_bytes.decode("utf-8", errors="replace").strip()
        except Exception:
            body = ""

        # Try to extract the 'detail' field from the JSON body (FastAPI convention).
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
    def _build_volumes(videos_dir: Path | None) -> dict | None:
        if videos_dir is None:
            return None
        return {str(videos_dir.resolve()): {"bind": "/data/videos", "mode": "ro"}}


# Singleton used by ModelRegistryService
docker_lifecycle_service = DockerLifecycleService()
