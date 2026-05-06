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
    ModelRuntime,
    ModelStatusUpdateResponse,
    ModelUiConfig,
    RegisteredModel,
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
        self.models_store_dir = (
            Path(settings.models_store_dir).resolve()
            if settings.models_store_dir
            else app_dir / "models_store"
        )
        self.installed_dir = self.models_store_dir / "installed"
        self.registry_path = self.models_store_dir / "registry.json"
        self._lock = Lock()
        self._models: dict[tuple[str, str], InstalledModel] = {}

        self._ensure_store()
        self._load_registry()
        self._seed_default_models()

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
            logger.warning("Registry file could not be loaded, starting with built-in models: %s", exc)
            models = []

        self._models = {(model.model_id, model.version): model for model in models}

    def _seed_default_models(self) -> None:
        key = ("dummy_lsec_segmenter", "0.1.0")
        existing_model = self._models.get(key)
        if existing_model is not None and existing_model.source != "builtin":
            return

        status = existing_model.status if existing_model is not None else "available"
        installed_at = existing_model.installed_at if existing_model is not None else self._utc_now()
        dummy_model = InstalledModel(
            model_id="dummy_lsec_segmenter",
            name="Dummy LSEC Segmenter",
            version="0.1.0",
            task="video_segmentation",
            runtime=ModelRuntime(mode="dummy", framework="dummy"),
            artifacts={"runner": "builtin://dummy_lsec_segmenter"},
            input_contract={
                "media_type": "video",
                "layout": "B,T,C,H,W",
                "window_size": 16,
                "channels": 3,
                "height": 224,
                "width": 224,
            },
            output_contract={
                "type": "frame_probabilities",
                "classes": ["background", "gesture"],
            },
            ui=ModelUiConfig(default_label="LSEC_REGION", supports_threshold=True),
            status=status,
            installed_at=installed_at,
            install_path=None,
            source="builtin",
        )
        self._models[key] = dummy_model
        self._save_registry()
        logger.info("Seeded or synchronized built-in dummy model '%s'.", dummy_model.model_id)

    def list_models(self) -> list[RegisteredModel]:
        models = sorted(
            self._models.values(),
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
                manifest = self._read_manifest(package=package, file_names=file_names)
                self._validate_artifacts(manifest=manifest, file_names=file_names)
                model = self._install_validated_package(package=package, manifest=manifest)
        except zipfile.BadZipFile as exc:
            raise ModelPackageInvalidError(f"Uploaded file '{filename}' is not a valid zip package.") from exc

        logger.info("Installed model '%s' version '%s'.", model.model_id, model.version)
        return ModelInstallResponse(message="Model installed successfully.", model=model)

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
    ) -> InstalledModel:
        install_path = self.installed_dir / manifest.model_id / manifest.version
        self._assert_path_inside(install_path, self.installed_dir)

        with self._lock:
            if (manifest.model_id, manifest.version) in self._models:
                raise ModelAlreadyExistsError(
                    f"Model '{manifest.model_id}' version '{manifest.version}' is already installed."
                )
            if install_path.exists():
                raise ModelAlreadyExistsError(
                    f"Install directory for model '{manifest.model_id}' version '{manifest.version}' already exists."
                )

            try:
                install_path.mkdir(parents=True, exist_ok=False)
                self._extract_package(package=package, target_dir=install_path)
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

    def _read_manifest(self, package: zipfile.ZipFile, file_names: set[str]) -> ModelManifest:
        if "manifest.json" not in file_names:
            raise ModelManifestNotFoundError("Model package must contain manifest.json at the zip root.")

        try:
            with package.open("manifest.json") as manifest_file:
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
            normalized_path = self._normalize_package_path(artifact_path)
            if normalized_path not in file_names:
                raise ModelArtifactMissingError(
                    f"Artifact '{artifact_name}' declared at '{artifact_path}' was not found in the package."
                )

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

    def _extract_package(self, package: zipfile.ZipFile, target_dir: Path) -> None:
        for entry in package.infolist():
            normalized_name = self._normalize_package_path(entry.filename)
            destination = target_dir / normalized_name
            self._assert_path_inside(destination, target_dir)

            if entry.is_dir():
                destination.mkdir(parents=True, exist_ok=True)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with package.open(entry) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)

    def _normalize_package_path(self, value: str) -> str:
        if not value or not value.strip():
            raise ModelPackageInvalidError("Package contains an empty path.")
        if "\\" in value:
            raise ModelPackageInvalidError(f"Unsafe package path '{value}' is not allowed.")
        if PureWindowsPath(value).drive:
            raise ModelPackageInvalidError(f"Unsafe package path '{value}' is not allowed.")

        path = PurePosixPath(value)
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
