import logging
from time import perf_counter

from app.runners.runner_selector import RunnerSelector, runner_selector
from app.schemas.inference import InferenceInput, InferenceOutput
from app.schemas.jobs import (
    ExecutionTrace,
    JobStatus,
    SegmentVideoRequest,
    SegmentVideoResponse,
)
from app.schemas.metrics import StageMetrics
from app.services.docker_service import (
    DockerServiceError,
    DockerTimeoutError,
    UnsupportedDockerContractError,
)
from app.services.job_queue import job_queue
from app.services.metrics_service import metrics_service
from app.services.model_registry_service import ModelRegistryService, model_registry_service
from app.storage.memory_store import MemoryStore, memory_store


logger = logging.getLogger(__name__)


class JobNotFoundError(Exception):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Job '{job_id}' was not found.")
        self.job_id = job_id


class JobService:
    def __init__(
        self,
        store: MemoryStore,
        registry_service: ModelRegistryService,
        selector: RunnerSelector,
    ) -> None:
        self.store = store
        self.registry_service = registry_service
        self.selector = selector

    def create_segment_video_job(self, request: SegmentVideoRequest) -> SegmentVideoResponse:
        total_started_at = perf_counter()
        state_history: list[str] = []

        # Registrar en métricas que llegó un nuevo job.
        metrics_service.record_started()

        self._transition(request.job_id, JobStatus.RECEIVED, state_history)

        # ── Validación (fuera de la cola — falla rápido sin ocupar slot) ──
        validation_started_at = perf_counter()
        self._transition(request.job_id, JobStatus.VALIDATING, state_history)
        model = self.registry_service.get_available_model(
            model_id=request.model.model_id,
            version=request.model.version,
        )
        validation_ms = self._elapsed_ms(validation_started_at)

        runner = self.selector.select(model=model)
        self._transition(request.job_id, JobStatus.PREPROCESSING, state_history)

        # ── Construcción del input de inferencia (fuera de la cola) ───────
        # Construir el dict de artefactos.  Si el manifest omite
        # "docker_image" (manifests que guardan el nombre en backend_config),
        # se deriva automáticamente para que DockerRunner pueda localizar la
        # imagen.
        artifacts: dict[str, str] = dict(model.artifacts)
        if "docker_image" not in artifacts:
            backend_cfg = self._extra_dict(model, "backend_config")
            if backend_cfg:
                img_name = (
                    str(backend_cfg.get("docker_image_name") or model.model_id)
                    .lower()
                    .replace("_", "-")
                )
                img_tag = str(backend_cfg.get("docker_image_tag") or model.version)
                artifacts["docker_image"] = f"{img_name}:{img_tag}"
                logger.debug(
                    "Derived docker_image='%s' from backend_config for model '%s'.",
                    artifacts["docker_image"],
                    model.model_id,
                )

        inference_input = InferenceInput(
            job_id=request.job_id,
            media_path=request.media.path,
            model_id=model.model_id,
            model_version=model.version,
            runtime_mode=model.runtime.mode,
            runtime_framework=model.runtime.framework,
            device_preference=request.execution.device_preference,
            runner_preference=request.execution.runner,
            timeout_sec=request.execution.timeout_sec,
            artifacts=artifacts,
            annotation=request.annotation.model_dump(),
            parameters=request.parameters.model_dump(),
            container=self._extra_dict(model, "container"),
            model_install_path=self.registry_service.resolve_install_path(model),
        )

        # ── Cola FIFO con control de concurrencia ─────────────────────────
        # Los jobs esperan aquí (bloqueando el hilo HTTP) hasta que haya un
        # slot disponible.  El orden de despacho es FIFO estricto.
        # Esto implementa el "algoritmo de gestión de colas" del objetivo 2
        # de la tesis y el control de VRAM (máx. N backends corriendo a la vez).
        self._transition(request.job_id, JobStatus.QUEUED, state_history)
        queue_entered_at = perf_counter()

        # Variables mutables para capturar tiempos desde dentro del closure.
        queue_wait_ms_ref: list[int] = []
        inference_elapsed_ref: list[int] = []

        def _run_inference() -> InferenceOutput:
            # Este callback se ejecuta cuando el job sale de la cola
            # y obtiene su slot de concurrencia.
            queue_wait_ms_ref.append(self._elapsed_ms(queue_entered_at))
            self._transition(request.job_id, JobStatus.RUNNING, state_history)
            t = perf_counter()
            result = runner.run(request=inference_input)
            inference_elapsed_ref.append(self._elapsed_ms(t))
            return result

        try:
            inference_output = job_queue.submit(
                job_id=request.job_id,
                fn=_run_inference,
            )
        except DockerTimeoutError:
            # Timeout del backend: estado TIMEOUT, no FAILED.
            # Permite distinguir "modelo lento / caído" de "error funcional".
            metrics_service.record_timeout("DOCKER_TIMEOUT")
            raise
        except DockerServiceError as exc:
            # Cualquier otro error Docker: estado FAILED.
            metrics_service.record_failed(exc.error_code)
            raise
        except Exception:
            metrics_service.record_failed("INTERNAL_SERVER_ERROR")
            raise

        # Extraer tiempos registrados desde el closure.
        queue_ms = queue_wait_ms_ref[0] if queue_wait_ms_ref else 0
        runner_metrics = inference_output.metrics
        inference_ms = max(
            runner_metrics.inference_ms,
            inference_elapsed_ref[0] if inference_elapsed_ref else 0,
        )

        # ── Postprocesamiento ─────────────────────────────────────────────
        postprocessing_started_at = perf_counter()
        self._transition(request.job_id, JobStatus.POSTPROCESSING, state_history)
        if not self._is_segment_output(inference_output.output_type):
            raise UnsupportedDockerContractError(
                "Final model backends must return media_info and segments. "
                f"Received output_type='{inference_output.output_type}'."
            )
        if inference_output.media_info is None:
            raise UnsupportedDockerContractError(
                "Final model backend response must include media_info."
            )
        segments = inference_output.segments
        postprocessing_ms = self._elapsed_ms(postprocessing_started_at)

        # ── Completado ────────────────────────────────────────────────────
        self._transition(request.job_id, JobStatus.COMPLETED, state_history)
        measured_total_ms = self._elapsed_ms(total_started_at)
        stage_total_ms = (
            validation_ms
            + queue_ms
            + runner_metrics.container_start_ms
            + runner_metrics.healthcheck_ms
            + runner_metrics.docker_inference_ms
            + postprocessing_ms
        )
        total_ms = max(measured_total_ms, stage_total_ms)
        media_info = inference_output.media_info

        response = SegmentVideoResponse(
            job_id=request.job_id,
            status=JobStatus.COMPLETED,
            media_info=media_info,
            segments=segments,
            trace=ExecutionTrace(
                runner=runner.runner_name,
                device=runner.device,
                model_id=model.model_id,
                model_version=model.version,
                output_type=inference_output.output_type,
                exec_ms=total_ms,
                stages=StageMetrics(
                    validation_ms=validation_ms,
                    queue_ms=queue_ms,
                    inference_ms=inference_ms,
                    postprocessing_ms=postprocessing_ms,
                    container_start_ms=runner_metrics.container_start_ms,
                    healthcheck_ms=runner_metrics.healthcheck_ms,
                    docker_inference_ms=runner_metrics.docker_inference_ms,
                    total_ms=total_ms,
                ),
                state_history=state_history,
                fps=media_info.fps,
                total_frames=media_info.total_frames,
                n_detected_segments=(
                    len(segments)
                    if self._is_segment_output(inference_output.output_type)
                    else None
                ),
                docker_mode=self._trace_string(
                    inference_output.runner_trace.get("docker_mode")
                ),
                docker_image=self._trace_string(
                    inference_output.runner_trace.get("docker_image")
                ),
                container_id=self._trace_string(
                    inference_output.runner_trace.get("container_id")
                ),
                container_start_ms=runner_metrics.container_start_ms,
                healthcheck_ms=runner_metrics.healthcheck_ms,
                docker_inference_ms=runner_metrics.docker_inference_ms,
                total_ms=total_ms,
            ),
        )

        self.store.save_job(response)
        logger.info("Job '%s' stored with status '%s'.", response.job_id, response.status.value)

        # Registrar en métricas el tiempo total del job completado.
        metrics_service.record_completed(total_ms)

        return response

    def get_job(self, job_id: str) -> SegmentVideoResponse:
        job = self.store.get_job(job_id)
        if job is None:
            raise JobNotFoundError(job_id=job_id)
        return job

    def _transition(self, job_id: str, status: JobStatus, state_history: list[str]) -> None:
        state_history.append(status.value)
        logger.info("Job '%s' transitioned to '%s'.", job_id, status.value)

    @staticmethod
    def _is_segment_output(output_type: str) -> bool:
        return output_type in {"segments", "segments_with_gloss"}

    @staticmethod
    def _extra_dict(model: object, field_name: str) -> dict[str, object]:
        value = getattr(model, field_name, None)
        if value is None:
            extras = getattr(model, "model_extra", None)
            if isinstance(extras, dict):
                value = extras.get(field_name)
        return dict(value) if isinstance(value, dict) else {}

    @staticmethod
    def _trace_string(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))


job_service = JobService(
    store=memory_store,
    registry_service=model_registry_service,
    selector=runner_selector,
)
