"""
BaseRunner — abstracción del mecanismo de ejecución de inferencias.

Define el contrato mínimo que todo runner debe cumplir. En la implementación
final el único runner activo es ``DockerRunner`` (``docker_http``), pero esta
abstracción permite incorporar otros mecanismos (p. ej. ONNX local o gRPC)
sin cambiar la capa HTTP ni a ELAN (TIC, decisión de escalabilidad).
"""
from abc import ABC, abstractmethod

from app.schemas.inference import InferenceInput, InferenceOutput


class BaseRunner(ABC):
    runner_name: str
    device: str

    @abstractmethod
    def run(self, request: InferenceInput) -> InferenceOutput:
        """Ejecuta la inferencia y devuelve el contrato interno de salida."""
