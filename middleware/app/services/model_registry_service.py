import logging
from typing import List

from app.schemas.models import RegisteredModel
from app.storage.memory_store import MemoryStore, memory_store


logger = logging.getLogger(__name__)


class ModelNotFoundError(Exception):
    def __init__(self, model_id: str, version: str | None = None) -> None:
        version_detail = f" version '{version}'" if version else ""
        super().__init__(f"Model '{model_id}'{version_detail} was not found.")
        self.model_id = model_id
        self.version = version


class ModelRegistryService:
    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self._seed_default_models()

    def _seed_default_models(self) -> None:
        if self.store.get_model("dummy_lsec_segmenter") is not None:
            return

        dummy_model = RegisteredModel(
            model_id="dummy_lsec_segmenter",
            name="Dummy LSEC Segmenter",
            version="0.1.0",
            task="video_segmentation",
            runtime="dummy",
            status="available",
        )
        self.store.save_model(dummy_model)
        logger.info("Seeded default dummy model '%s'.", dummy_model.model_id)

    def list_models(self) -> List[RegisteredModel]:
        return self.store.list_models()

    def get_model(self, model_id: str, version: str | None = None) -> RegisteredModel:
        model = self.store.get_model(model_id)
        if model is None:
            raise ModelNotFoundError(model_id=model_id, version=version)
        if version is not None and model.version != version:
            raise ModelNotFoundError(model_id=model_id, version=version)
        return model


model_registry_service = ModelRegistryService(store=memory_store)
