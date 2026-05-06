from app.runners.base_runner import BaseRunner
from app.runners.dummy_runner import DummyRunner
from app.runners.keypoint_pipeline_runner import KeypointPipelineRunner
from app.runners.native_pytorch_runner import NativePyTorchRunner
from app.schemas.models import InstalledModel


class RunnerSelectionError(Exception):
    error_code = "UNSUPPORTED_RUNTIME"
    status_code = 501

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class UnsupportedFrameworkError(RunnerSelectionError):
    error_code = "UNSUPPORTED_FRAMEWORK"
    status_code = 501


class RunnerSelector:
    def select(self, model: InstalledModel) -> BaseRunner:
        if model.runtime.mode == "dummy":
            return DummyRunner()
        if model.runtime.mode == "native":
            if model.runtime.runner == "keypoint_pipeline":
                return KeypointPipelineRunner()
            if model.runtime.framework == "pytorch":
                return NativePyTorchRunner()
            raise UnsupportedFrameworkError(
                f"Runtime framework '{model.runtime.framework}' is not supported for native execution."
            )
        if model.runtime.mode == "docker":
            raise RunnerSelectionError("Docker runtime will be available in a future phase.")
        raise RunnerSelectionError(f"Runtime mode '{model.runtime.mode}' is not supported.")


runner_selector = RunnerSelector()
