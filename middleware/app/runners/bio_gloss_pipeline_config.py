from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any


DEFAULT_POSE_IDX = (0, 11, 12, 13, 14, 15, 16, 23, 24, 25, 26, 27, 28)


@dataclass(frozen=True)
class BioGlossPipelineConfig:
    bio_window_size: int = 64
    bio_stride: int = 32
    gloss_max_len: int = 72
    num_bio_classes: int = 3
    smooth_kernel: int = 3
    min_segment_len: int = 4
    max_gap_fill: int = 0
    min_i_after_b: int = 3
    suppress_repeated_b_inside_segment: bool = False
    top_k: int = 5
    pose_idx: tuple[int, ...] = DEFAULT_POSE_IDX
    raw_feature_dim: int = 178
    final_feature_dim: int = 356
    add_dynamic_features: bool = True
    bio_hidden_dim: int = 128
    bio_num_layers: int = 2
    bio_dropout: float = 0.2
    gloss_d_model: int = 256
    gloss_nhead: int = 8
    gloss_num_layers: int = 4
    gloss_dim_feedforward: int = 512
    gloss_dropout: float = 0.2
    gloss_positional_max_len: int = 512

    @classmethod
    def from_sources(
        cls,
        artifact_config: dict[str, Any],
        request_parameters: dict[str, object],
    ) -> "BioGlossPipelineConfig":
        values = {field.name: getattr(cls(), field.name) for field in fields(cls)}
        allowed = set(values)
        for source in (artifact_config, request_parameters):
            for key, value in source.items():
                if key in allowed and value is not None:
                    values[key] = value
        return cls(**cls._coerce(values)).validate()

    def validate(self) -> "BioGlossPipelineConfig":
        positive_ints = [
            "bio_window_size",
            "bio_stride",
            "gloss_max_len",
            "num_bio_classes",
            "raw_feature_dim",
            "final_feature_dim",
            "bio_hidden_dim",
            "bio_num_layers",
            "gloss_d_model",
            "gloss_nhead",
            "gloss_num_layers",
            "gloss_dim_feedforward",
            "gloss_positional_max_len",
            "top_k",
        ]
        for field_name in positive_ints:
            if getattr(self, field_name) <= 0:
                raise ValueError(f"Pipeline config field '{field_name}' must be greater than zero.")
        if self.smooth_kernel <= 0:
            raise ValueError("Pipeline config field 'smooth_kernel' must be greater than zero.")
        if self.min_segment_len < 0 or self.max_gap_fill < 0 or self.min_i_after_b < 0:
            raise ValueError("Pipeline postprocessing lengths must be greater than or equal to zero.")
        if len(self.pose_idx) != 13:
            raise ValueError("Pipeline config field 'pose_idx' must contain 13 pose landmark indices.")
        if self.add_dynamic_features and self.final_feature_dim != self.raw_feature_dim * 2:
            raise ValueError("Dynamic-feature pipelines must have final_feature_dim == raw_feature_dim * 2.")
        return self

    @staticmethod
    def _coerce(values: dict[str, Any]) -> dict[str, Any]:
        integer_fields = {
            "bio_window_size",
            "bio_stride",
            "gloss_max_len",
            "num_bio_classes",
            "smooth_kernel",
            "min_segment_len",
            "max_gap_fill",
            "min_i_after_b",
            "top_k",
            "raw_feature_dim",
            "final_feature_dim",
            "bio_hidden_dim",
            "bio_num_layers",
            "gloss_d_model",
            "gloss_nhead",
            "gloss_num_layers",
            "gloss_dim_feedforward",
            "gloss_positional_max_len",
        }
        float_fields = {"bio_dropout", "gloss_dropout"}
        coerced = dict(values)
        for field_name in integer_fields:
            coerced[field_name] = int(coerced[field_name])
        for field_name in float_fields:
            coerced[field_name] = float(coerced[field_name])
        coerced["pose_idx"] = tuple(int(value) for value in coerced["pose_idx"])
        coerced["add_dynamic_features"] = bool(coerced["add_dynamic_features"])
        coerced["suppress_repeated_b_inside_segment"] = bool(
            coerced["suppress_repeated_b_inside_segment"]
        )
        return coerced
