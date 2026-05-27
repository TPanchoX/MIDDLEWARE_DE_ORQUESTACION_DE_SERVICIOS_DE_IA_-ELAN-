from app.runners.base_runner import BaseRunner
from app.runners.docker_runner import DockerRunner
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
        if model.runtime.mode == "docker":
            if model.runtime.framework == "container" and model.runtime.runner == "docker_http":
                return DockerRunner()
            raise RunnerSelectionError(
                "Docker runtime is supported only with runtime.framework='container' "
                "and runtime.runner='docker_http'."
            )
        raise RunnerSelectionError(
            "The final middleware only supports docker_http model backends. "
            f"Model '{model.model_id}' declares runtime.mode='{model.runtime.mode}'."
        )


runner_selector = RunnerSelector()
