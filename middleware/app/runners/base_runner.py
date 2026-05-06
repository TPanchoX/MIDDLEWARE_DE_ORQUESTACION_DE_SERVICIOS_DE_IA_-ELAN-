from abc import ABC, abstractmethod

from app.schemas.inference import InferenceInput, InferenceOutput


class BaseRunner(ABC):
    runner_name: str
    device: str

    @abstractmethod
    def run(self, request: InferenceInput) -> InferenceOutput:
        """Run inference and return an internal output contract."""
