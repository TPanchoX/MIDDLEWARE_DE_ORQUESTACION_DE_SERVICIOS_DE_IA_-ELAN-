import logging
from time import perf_counter

from app.processing.temporal_postprocessor import TemporalPostprocessor, temporal_postprocessor
from app.processing.video_pipeline import VideoPipeline, video_pipeline
from app.runners.runner_selector import RunnerSelector, runner_selector
from app.schemas.inference import InferenceInput
from app.schemas.jobs import (
    ExecutionTrace,
    JobStatus,
    MediaInfo,
    SegmentVideoRequest,
    SegmentVideoResponse,
)
from app.schemas.metrics import StageMetrics
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
        postprocessor: TemporalPostprocessor,
        pipeline: VideoPipeline,
    ) -> None:
        self.store = store
        self.registry_service = registry_service
        self.selector = selector
        self.postprocessor = postprocessor
        self.pipeline = pipeline

    def create_segment_video_job(self, request: SegmentVideoRequest) -> SegmentVideoResponse:
        total_started_at = perf_counter()
        state_history: list[str] = []

        self._transition(request.job_id, JobStatus.RECEIVED, state_history)

        validation_started_at = perf_counter()
        self._transition(request.job_id, JobStatus.VALIDATING, state_history)
        model = self.registry_service.get_available_model(
            model_id=request.model.model_id,
            version=request.model.version,
        )
        validation_ms = self._elapsed_ms(validation_started_at)

        self._transition(request.job_id, JobStatus.PREPROCESSING, state_history)
        video_result = self.pipeline.process(
            video_path=request.media.path,
            parameters=request.parameters,
        )

        queue_started_at = perf_counter()
        self._transition(request.job_id, JobStatus.QUEUED, state_history)
        runner = self.selector.select(model=model)
        queue_ms = self._elapsed_ms(queue_started_at)

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
            artifacts=model.artifacts,
            parameters=request.parameters.model_dump(),
            model_install_path=self.registry_service.resolve_install_path(model),
            video_metadata=video_result.metadata,
            video_processing_result=video_result,
            sampled_frames=video_result.sampled_frames_count,
            windows_count=video_result.windows_count,
        )

        inference_started_at = perf_counter()
        self._transition(request.job_id, JobStatus.RUNNING, state_history)
        inference_output = runner.run(request=inference_input)
        runner_metrics = inference_output.metrics
        if inference_output.output_type == "segments_with_gloss":
            inference_ms = runner_metrics.inference_ms
        else:
            inference_ms = max(
                runner_metrics.inference_ms,
                self._elapsed_ms(inference_started_at),
            )

        postprocessing_started_at = perf_counter()
        self._transition(request.job_id, JobStatus.POSTPROCESSING, state_history)
        frame_output = inference_output.frame_probabilities
        if inference_output.output_type == "segments_with_gloss":
            segments = inference_output.segments
        else:
            if frame_output is None:
                raise ValueError("Runner returned frame_probabilities output without frame probabilities.")
            segments = self.postprocessor.process(
                frame_output=frame_output,
                parameters=request.parameters,
                default_label=request.annotation.default_label,
            )
        postprocessing_ms = self._elapsed_ms(postprocessing_started_at)

        self._transition(request.job_id, JobStatus.COMPLETED, state_history)
        measured_total_ms = self._elapsed_ms(total_started_at)
        video_metrics = video_result.metrics
        if inference_output.output_type == "segments_with_gloss":
            stage_total_ms = (
                validation_ms
                + video_metrics.total_video_processing_ms
                + queue_ms
                + runner_metrics.vocab_load_ms
                + runner_metrics.bio_model_load_ms
                + runner_metrics.gloss_model_load_ms
                + runner_metrics.keypoint_extraction_ms
                + runner_metrics.bio_inference_ms
                + runner_metrics.bio_postprocessing_ms
                + runner_metrics.gloss_classification_ms
                + postprocessing_ms
            )
        else:
            stage_total_ms = (
                validation_ms
                + video_metrics.total_video_processing_ms
                + queue_ms
                + runner_metrics.model_load_ms
                + runner_metrics.tensor_conversion_ms
                + inference_ms
                + runner_metrics.aggregation_ms
                + postprocessing_ms
            )
        total_ms = max(measured_total_ms, stage_total_ms)
        media_info = inference_output.media_info
        if media_info is None:
            if frame_output is None:
                raise ValueError("Runner returned no media_info and no frame probabilities.")
            media_info = MediaInfo(
                fps=frame_output.fps,
                duration_ms=frame_output.duration_ms,
                total_frames=frame_output.total_frames,
            )

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
                    video_loading_ms=video_metrics.video_loading_ms,
                    frame_sampling_ms=video_metrics.frame_sampling_ms,
                    preprocessing_ms=video_metrics.preprocessing_ms,
                    window_building_ms=video_metrics.window_building_ms,
                    total_video_processing_ms=video_metrics.total_video_processing_ms,
                    model_load_ms=runner_metrics.model_load_ms,
                    tensor_conversion_ms=runner_metrics.tensor_conversion_ms,
                    aggregation_ms=runner_metrics.aggregation_ms,
                    validation_ms=validation_ms,
                    queue_ms=queue_ms,
                    inference_ms=inference_ms,
                    postprocessing_ms=postprocessing_ms,
                    keypoint_extraction_ms=runner_metrics.keypoint_extraction_ms,
                    bio_model_load_ms=runner_metrics.bio_model_load_ms,
                    gloss_model_load_ms=runner_metrics.gloss_model_load_ms,
                    vocab_load_ms=runner_metrics.vocab_load_ms,
                    bio_inference_ms=runner_metrics.bio_inference_ms,
                    bio_postprocessing_ms=runner_metrics.bio_postprocessing_ms,
                    gloss_classification_ms=runner_metrics.gloss_classification_ms,
                    total_ms=total_ms,
                ),
                state_history=state_history,
                fps=media_info.fps,
                total_frames=media_info.total_frames,
                sampled_frames=video_result.sampled_frames_count,
                windows_count=video_result.windows_count,
                original_width=video_result.metadata.width,
                original_height=video_result.metadata.height,
                n_detected_segments=len(segments) if inference_output.output_type == "segments_with_gloss" else None,
                keypoint_extraction_ms=runner_metrics.keypoint_extraction_ms or None,
                bio_model_load_ms=runner_metrics.bio_model_load_ms or None,
                gloss_model_load_ms=runner_metrics.gloss_model_load_ms or None,
                vocab_load_ms=runner_metrics.vocab_load_ms or None,
                bio_inference_ms=runner_metrics.bio_inference_ms or None,
                bio_postprocessing_ms=runner_metrics.bio_postprocessing_ms or None,
                gloss_classification_ms=runner_metrics.gloss_classification_ms or None,
                total_ms=total_ms,
            ),
        )
        self.store.save_job(response)
        logger.info("Job '%s' stored with status '%s'.", response.job_id, response.status.value)
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
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))


job_service = JobService(
    store=memory_store,
    registry_service=model_registry_service,
    selector=runner_selector,
    postprocessor=temporal_postprocessor,
    pipeline=video_pipeline,
)
