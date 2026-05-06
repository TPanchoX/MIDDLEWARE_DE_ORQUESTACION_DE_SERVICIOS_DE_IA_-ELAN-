from time import perf_counter

from app.processing.frame_preprocessor import FramePreprocessor, frame_preprocessor
from app.processing.frame_sampler import FrameSampler, frame_sampler
from app.processing.video_loader import VideoLoader, video_loader
from app.processing.window_builder import WindowBuilder, window_builder
from app.schemas.jobs import SegmentationParameters
from app.schemas.video import (
    FrameSamplingConfig,
    VideoProcessingMetrics,
    VideoProcessingResult,
    WindowConfig,
)


class VideoPipeline:
    def __init__(
        self,
        loader: VideoLoader,
        sampler: FrameSampler,
        preprocessor: FramePreprocessor,
        builder: WindowBuilder,
    ) -> None:
        self.loader = loader
        self.sampler = sampler
        self.preprocessor = preprocessor
        self.builder = builder

    def process(
        self,
        video_path: str,
        parameters: SegmentationParameters,
    ) -> VideoProcessingResult:
        total_started_at = perf_counter()

        loading_started_at = perf_counter()
        metadata = self.loader.load_metadata(video_path)
        video_loading_ms = self._elapsed_ms(loading_started_at)

        sampling_started_at = perf_counter()
        frames, frame_indices = self.sampler.sample(
            video_path=metadata.path,
            config=FrameSamplingConfig(
                max_frames=parameters.max_frames,
                frame_stride=parameters.frame_stride,
            ),
        )
        frame_sampling_ms = self._elapsed_ms(sampling_started_at)

        preprocessing_started_at = perf_counter()
        preprocessed_frames = self.preprocessor.preprocess(
            frames=frames,
            resize_width=parameters.resize_width,
            resize_height=parameters.resize_height,
        )
        preprocessing_ms = self._elapsed_ms(preprocessing_started_at)

        window_started_at = perf_counter()
        windows = self.builder.build(
            frames=preprocessed_frames,
            frame_indices=frame_indices,
            config=WindowConfig(
                window_size=parameters.window_size,
                stride=parameters.stride,
            ),
        )
        window_building_ms = self._elapsed_ms(window_started_at)

        total_video_processing_ms = self._elapsed_ms(total_started_at)
        return VideoProcessingResult(
            metadata=metadata,
            sampled_frame_indices=frame_indices,
            preprocessed_frames=preprocessed_frames,
            windows=windows,
            metrics=VideoProcessingMetrics(
                video_loading_ms=video_loading_ms,
                frame_sampling_ms=frame_sampling_ms,
                preprocessing_ms=preprocessing_ms,
                window_building_ms=window_building_ms,
                total_video_processing_ms=total_video_processing_ms,
            ),
        )

    @staticmethod
    def _elapsed_ms(started_at: float) -> int:
        return max(1, int(round((perf_counter() - started_at) * 1000)))


video_pipeline = VideoPipeline(
    loader=video_loader,
    sampler=frame_sampler,
    preprocessor=frame_preprocessor,
    builder=window_builder,
)
