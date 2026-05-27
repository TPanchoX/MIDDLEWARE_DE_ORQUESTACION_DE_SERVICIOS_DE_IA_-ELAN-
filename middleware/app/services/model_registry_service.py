from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
import json
import logging
from pathlib import Path, PurePosixPath, PureWindowsPath
import shutil
from threading import Lock
from typing import Iterable
import zipfile

from pydantic import ValidationError

from app.core.config import get_settings
from app.schemas.models import (
    InstalledModel,
    ModelInstallResponse,
    ModelListResponse,
    ModelManifest,
    ModelStatusUpdateResponse,
    RegisteredModel,
)
from app.services.docker_lifecycle_service import (
    DockerLifecycleError,
    docker_lifecycle_service,
)


logger = logging.getLogger(__name__)


class ModelRegistryError(Exception):
    error_code = "MODEL_PACKAGE_INVALID"
    status_code = 400

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class ModelPackageInvalidError(ModelRegistryError):
    error_code = "MODEL_PACKAGE_INVALID"
    status_code = 400


class ModelManifestNotFoundError(ModelRegistryError):
    error_code = "MODEL_MANIFEST_NOT_FOUND"
    status_code = 400


class ModelManifestInvalidError(ModelRegistryError):
    error_code = "MODEL_MANIFEST_INVALID"
    status_code = 400


class ModelArtifactMissingError(ModelRegistryError):
    error_code = "MODEL_ARTIFACT_MISSING"
    status_code = 400


class ModelAlreadyExistsError(ModelRegistryError):
    error_code = "MODEL_ALREADY_EXISTS"
    status_code = 409


class ModelNotFoundError(ModelRegistryError):
    error_code = "MODEL_NOT_FOUND"
    status_code = 404

    def __init__(self, model_id: str, version: str | None = None) -> None:
        version_detail = f" version '{version}'" if version else ""
        super().__init__(f"Model '{model_id}'{version_detail} was not found.")
        self.model_id = model_id
        self.version = version


class ModelDisabledError(ModelRegistryError):
    error_code = "MODEL_DISABLED"
    status_code = 409

    def __init__(self, model_id: str, version: str) -> None:
        super().__init__(f"Model '{model_id}' version '{version}' is disabled.")
        self.model_id = model_id
        self.version = version


class ModelRegistryService:
    def __init__(self) -> None:
        app_dir = Path(__file__).resolve().parents[1]
        settings = get_settings()
        self.runtime_profile = settings.runtime_profile
        self.models_store_dir = (
            Path(settings.models_store_dir).resolve()
            if settings.models_store_dir
            else app_dir / "models_store"
        )
        self.bootstrap_manifests_dir = (
            Path(settings.bootstrap_manifests_dir).resolve()
            if settings.bootstrap_manifests_dir
            else None
        )
        self.installed_dir = self.models_store_dir / "installed"
        self.registry_path = self.models_store_dir / "registry.json"
        self._lock = Lock()
        self._models: dict[tuple[str, str], InstalledModel] = {}

        self._ensure_store()
        self._load_registry()
        self._bootstrap_docker_manifests()

    def _ensure_store(self) -> None:
        self.installed_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._write_registry([])

    def _load_registry(self) -> None:
        try:
            raw_registry = json.loads(self.registry_path.read_text(encoding="utf-8"))
            raw_models = raw_registry.get("models", [])
            models = [InstalledModel.model_validate(item) for item in raw_models]
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            logger.warning("Registry file could not be loaded, starting with an empty registry: %s", exc)
            models = []

        self._models = {(model.model_id, model.version): model for model in models}

    def _bootstrap_docker_manifests(self) -> None:
        if self.bootstrap_manifests_dir is None:
            return
        if not self.bootstrap_manifests_dir.exists():
            logger.warning("Bootstrap manifest directory '%s' does not exist.", self.bootstrap_manifests_dir)
            return

        bootstrapped = False
        for manifest_path in sorted(self.bootstrap_manifests_dir.glob("*.json")):
            try:
                manifest_data = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
                manifest = ModelManifest.model_validate(manifest_data)
            except (OSError, json.JSONDecodeError, ValidationError) as exc:
                logger.warning("Bootstrap manifest '%s' is invalid and was skipped: %s", manifest_path, exc)
                continue

            if manifest.runtime.mode != "docker":
                logger.warning("Bootstrap manifest '%s' is not a docker model and was skipped.", manifest_path)
                continue

            key = (manifest.model_id, manifest.version)
            existing_model = self._models.get(key)
            if existing_model is not None and existing_model.runtime.mode == "docker":
                continue

            self._models[key] = InstalledModel(
                **manifest.model_dump(),
                status="available",
                installed_at=self._utc_now(),
                install_path=None,
                source="installed",
            )
            bootstrapped = True
            logger.info(
                "Bootstrapped docker model '%s' version '%s' from '%s'.",
                manifest.model_id,
                manifest.version,
                manifest_path,
            )

        if bootstrapped:
            self._save_registry()

    def list_models(self) -> list[RegisteredModel]:
        available_models = self._models.values()
        if self.runtime_profile in {"final", "production", "docker"}:
            available_models = [
                model
                for model in available_models
                if model.runtime.mode == "docker" and model.runtime.runner == "docker_http"
            ]

        models = sorted(
            available_models,
            key=lambda item: (item.source != "builtin", item.model_id, item.version),
        )
        return [
            RegisteredModel(
                model_id=model.model_id,
                name=model.name,
                version=model.version,
                task=model.task,
                runtime=model.runtime.mode,
                status=model.status,
            )
            for model in models
        ]

    def list_models_response(self) -> ModelListResponse:
        return ModelListResponse(models=self.list_models())

    def get_model(self, model_id: str, version: str | None = None) -> InstalledModel:
        with self._lock:
            return self._get_model_unlocked(model_id=model_id, version=version)

    def get_available_model(self, model_id: str, version: str | None = None) -> InstalledModel:
        model = self.get_model(model_id=model_id, version=version)
        if model.status == "disabled":
            raise ModelDisabledError(model_id=model.model_id, version=model.version)
        if model.status != "available":
            raise ModelNotFoundError(model_id=model_id, version=version)
        return model

    def install_model_package(self, filename: str, content: bytes) -> ModelInstallResponse:
        if not content:
            raise ModelPackageInvalidError("Uploaded model package is empty.")

        try:
            with zipfile.ZipFile(BytesIO(content)) as package:
                file_names = self._validate_zip_entries(package.infolist())

                # Auto-detect a common top-level directory that wraps all files.
                # ZIP files created with Windows Explorer, Compress-Archive (without \*),
                # or macOS "Compress" all wrap everything inside a folder.
                # Strip it transparently so the manifest is always at logical root.
                zip_prefix = self._detect_zip_prefix(file_names)
                effective_names = (
                    {name[len(zip_prefix):] for name in file_names if name != zip_prefix}
                    if zip_prefix else file_names
                )

                manifest = self._read_manifest(
                    package=package, file_names=effective_names, zip_prefix=zip_prefix
                )
                self._validate_artifacts(manifest=manifest, file_names=effective_names)
                model = self._install_validated_package(
                    package=package, manifest=manifest, zip_prefix=zip_prefix
                )
        except zipfile.BadZipFile as exc:
            raise ModelPackageInvalidError(f"Uploaded file '{filename}' is not a valid zip package.") from exc

        # Auto-build and start Docker container when the package includes a Dockerfile.
        # This is the "install once, use always" flow: POST /models/install → docker build
        # → docker run → health check → ready to serve inference requests.
        if "dockerfile" in model.artifacts:
            install_path = Path(self.resolve_install_path(model))
            self._auto_start_docker_backend(model=model, manifest=manifest, install_path=install_path)

        logger.info("Installed model '%s' version '%s'.", model.model_id, model.version)
        return ModelInstallResponse(message="Model installed successfully.", model=model)

    def _auto_start_docker_backend(
        self,
        model: InstalledModel,
        manifest: ModelManifest,
        install_path: Path,
    ) -> None:
        """Build Docker image and start container for a self-contained model package."""
        settings = get_settings()
        videos_dir = Path(settings.videos_dir).resolve() if settings.videos_dir else None

        backend_config: dict = {}
        if manifest.model_extra:
            raw = manifest.model_extra.get("backend_config")
            if isinstance(raw, dict):
                backend_config = raw

        logger.info(
            "Starting Docker lifecycle for model '%s' version '%s'.",
            model.model_id, model.version,
        )
        try:
            docker_lifecycle_service.build_and_start(
                install_path=install_path,
                model_id=model.model_id,
                model_version=model.version,
                backend_config=backend_config,
                videos_dir=videos_dir,
            )
        except DockerLifecycleError as exc:
            self._rollback_installation(model=model, install_path=install_path)
            raise ModelPackageInvalidError(
                f"Docker lifecycle failed — model installation rolled back. Detail: {exc.detail}"
            ) from exc
        except Exception as exc:
            self._rollback_installation(model=model, install_path=install_path)
            raise ModelPackageInvalidError(
                f"Unexpected error during Docker lifecycle — installation rolled back: {exc}"
            ) from exc

    def _rollback_installation(self, model: InstalledModel, install_path: Path) -> None:
        """Remove model from the in-memory registry, persist, and delete the install dir."""
        logger.warning(
            "Rolling back installation of model '%s' version '%s'.",
            model.model_id, model.version,
        )
        with self._lock:
            self._models.pop((model.model_id, model.version), None)
            self._save_registry()
        if install_path.exists():
            shutil.rmtree(install_path, ignore_errors=True)

    def update_status(
        self,
        model_id: str,
        status: str,
        version: str | None = None,
    ) -> ModelStatusUpdateResponse:
        with self._lock:
            model = self._get_model_unlocked(model_id=model_id, version=version)
            updated_model = model.model_copy(update={"status": status})
            self._models[(updated_model.model_id, updated_model.version)] = updated_model
            self._save_registry()

        logger.info(
            "Model '%s' version '%s' changed status to '%s'.",
            updated_model.model_id,
            updated_model.version,
            updated_model.status,
        )
        return ModelStatusUpdateResponse(message="Model status updated successfully.", model=updated_model)

    def resolve_install_path(self, model: InstalledModel) -> str | None:
        if model.install_path is None:
            return None

        path = Path(model.install_path)
        if path.is_absolute():
            return str(path.resolve())

        app_dir = Path(__file__).resolve().parents[1]
        return str((app_dir / path).resolve())

    def _get_model_unlocked(self, model_id: str, version: str | None = None) -> InstalledModel:
        if version is not None:
            model = self._models.get((model_id, version))
            if model is None:
                raise ModelNotFoundError(model_id=model_id, version=version)
            return model

        matches = [model for model in self._models.values() if model.model_id == model_id]
        if not matches:
            raise ModelNotFoundError(model_id=model_id)
        return sorted(matches, key=lambda item: item.version, reverse=True)[0]

    def _install_validated_package(
        self,
        package: zipfile.ZipFile,
        manifest: ModelManifest,
        zip_prefix: str = "",
    ) -> InstalledModel:
        install_path = self.installed_dir / manifest.model_id / manifest.version
        self._assert_path_inside(install_path, self.installed_dir)

        with self._lock:
            # Guard against stale in-memory entries that survived a failed rollback.
            # If the registry file no longer contains this model but _models does,
            # the in-memory state is out of sync — heal it before raising.
            if (manifest.model_id, manifest.version) in self._models:
                persisted = any(
                    m.get("model_id") == manifest.model_id
                    and m.get("version") == manifest.version
                    for m in json.loads(
                        self.registry_path.read_text(encoding="utf-8")
                    ).get("models", [])
                )
                if not persisted:
                    # Stale in-memory entry — remove it silently and proceed.
                    logger.warning(
                        "Removing stale in-memory entry for '%s' v%s (not in registry.json).",
                        manifest.model_id, manifest.version,
                    )
                    self._models.pop((manifest.model_id, manifest.version), None)
                else:
                    raise ModelAlreadyExistsError(
                        f"Model '{manifest.model_id}' version '{manifest.version}' is already installed."
                    )
            if install_path.exists():
                # Orphan directory from a failed rollback — clean it up.
                logger.warning(
                    "Removing orphan install directory for '%s' v%s.",
                    manifest.model_id, manifest.version,
                )
                shutil.rmtree(install_path, ignore_errors=True)

            try:
                install_path.mkdir(parents=True, exist_ok=False)
                self._extract_package(package=package, target_dir=install_path, zip_prefix=zip_prefix)
                installed_model = InstalledModel(
                    **manifest.model_dump(),
                    status="available",
                    installed_at=self._utc_now(),
                    install_path=self._relative_to_app(install_path),
                    source="installed",
                )
                self._models[(installed_model.model_id, installed_model.version)] = installed_model
                self._save_registry()
            except Exception:
                if install_path.exists():
                    shutil.rmtree(install_path)
                raise

        return installed_model

    def _read_manifest(
        self,
        package: zipfile.ZipFile,
        file_names: set[str],
        zip_prefix: str = "",
    ) -> ModelManifest:
        if "manifest.json" not in file_names:
            raise ModelManifestNotFoundError("Model package must contain manifest.json at the zip root.")

        try:
            with package.open(f"{zip_prefix}manifest.json") as manifest_file:
                manifest_data = json.loads(manifest_file.read().decode("utf-8-sig"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ModelManifestInvalidError("manifest.json must be valid UTF-8 JSON.") from exc

        try:
            return ModelManifest.model_validate(manifest_data)
        except ValidationError as exc:
            invalid_fields = sorted({".".join(str(part) for part in error["loc"]) for error in exc.errors()})
            detail = "manifest.json is missing required fields or has invalid values."
            if invalid_fields:
                detail = f"{detail} Fields: {', '.join(invalid_fields)}."
            raise ModelManifestInvalidError(detail) from exc

    def _validate_artifacts(self, manifest: ModelManifest, file_names: set[str]) -> None:
        for artifact_name, artifact_path in manifest.artifacts.items():
            if self._is_external_docker_artifact(manifest=manifest, artifact_name=artifact_name):
                continue
            normalized_path = self._normalize_package_path(artifact_path)
            if normalized_path not in file_names:
                raise ModelArtifactMissingError(
                    f"Artifact '{artifact_name}' declared at '{artifact_path}' was not found in the package."
                )

    @staticmethod
    def _is_external_docker_artifact(manifest: ModelManifest, artifact_name: str) -> bool:
        return manifest.runtime.mode == "docker" and artifact_name == "docker_image"

    def _validate_zip_entries(self, entries: Iterable[zipfile.ZipInfo]) -> set[str]:
        file_names: set[str] = set()
        has_files = False

        for entry in entries:
            normalized_name = self._normalize_package_path(entry.filename)
            if entry.is_dir():
                continue
            has_files = True
            file_names.add(normalized_name)

        if not has_files:
            raise ModelPackageInvalidError("Model package does not contain files.")
        return file_names

    def _extract_package(
        self,
        package: zipfile.ZipFile,
        target_dir: Path,
        zip_prefix: str = "",
    ) -> None:
        for entry in package.infolist():
            normalized_name = self._normalize_package_path(entry.filename)

            # Strip the common top-level prefix that was detected during validation.
            if zip_prefix and normalized_name.startswith(zip_prefix):
                normalized_name = normalized_name[len(zip_prefix):]

            # Skip the prefix directory entry itself (empty after stripping).
            if not normalized_name:
                continue

            destination = target_dir / normalized_name
            self._assert_path_inside(destination, target_dir)

            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with package.open(entry) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)

    @staticmethod
    def _detect_zip_prefix(file_names: set[str]) -> str:
        """
        Return the common top-level directory (with trailing ``/``) shared by
        ALL entries, or an empty string if no such prefix exists.

        Examples
        --------
        ``{"pkg/manifest.json", "pkg/config/x.json"}``  →  ``"pkg/"``
        ``{"manifest.json", "config/x.json"}``           →  ``""``

        This lets the service accept ZIP files that wrap all content inside
        a single folder (the default behaviour of Windows Explorer,
        ``Compress-Archive`` without ``\\*``, and macOS "Compress").
        """
        if not file_names:
            return ""

        def _top_dir(name: str) -> str:
            idx = name.find("/")
            return name[: idx + 1] if idx >= 0 else ""

        top_dirs = {_top_dir(name) for name in file_names}
        if len(top_dirs) == 1:
            prefix = top_dirs.pop()
            # Only strip if EVERY file lives below a real subdirectory
            # (prefix == "" means all files are already at the root).
            return prefix
        return ""

    def _normalize_package_path(self, value: str) -> str:
        if not value or not value.strip():
            raise ModelPackageInvalidError("Package contains an empty path.")

        # ZIP files created on Windows (Compress-Archive, Explorer, etc.) store paths with
        # backslashes. Normalise to forward slashes before applying security checks so that
        # valid packages from Windows hosts are not rejected.
        normalized = value.replace("\\", "/")

        # Reject Windows drive letters (e.g. "C:/foo") even after normalisation.
        if PureWindowsPath(normalized).drive:
            raise ModelPackageInvalidError(f"Unsafe package path '{value}' is not allowed.")

        path = PurePosixPath(normalized)
        if path.is_absolute():
            raise ModelPackageInvalidError(f"Unsafe package path '{value}' is not allowed.")

        parts = [part for part in path.parts if part not in ("", ".")]
        if not parts or ".." in parts:
            raise ModelPackageInvalidError(f"Unsafe package path '{value}' is not allowed.")

        return PurePosixPath(*parts).as_posix()

    def _save_registry(self) -> None:
        models = sorted(self._models.values(), key=lambda item: (item.model_id, item.version))
        self._write_registry([model.model_dump(mode="json") for model in models])

    def _write_registry(self, models: list[dict]) -> None:
        self.models_store_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path.write_text(
            json.dumps({"models": models}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _relative_to_app(self, path: Path) -> str:
        app_dir = Path(__file__).resolve().parents[1]
        resolved_path = path.resolve()
        try:
            return resolved_path.relative_to(app_dir).as_posix()
        except ValueError:
            return resolved_path.as_posix()

    def _assert_path_inside(self, candidate: Path, parent: Path) -> None:
        try:
            candidate.resolve().relative_to(parent.resolve())
        except ValueError as exc:
            raise ModelPackageInvalidError(f"Unsafe package path '{candidate}' is not allowed.") from exc

    def _utc_now(self) -> str:
        return datetime.now(UTC).isoformat().replace("+00:00", "Z")


model_registry_service = ModelRegistryService()
