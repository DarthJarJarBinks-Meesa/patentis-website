"""Masked patent supervision configuration (see patentis-cursor-prompt.md)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class MaskingStrategy(Enum):
    RANDOM = "random"
    TEMPORAL = "temporal"
    CITATION_SPARSE = "sparse"


@dataclass
class MaskingConfig:
    strategy: MaskingStrategy = MaskingStrategy.TEMPORAL
    n_hidden_min: int = 5
    n_hidden_max: int = 10
    min_region_size: int = 40
    min_visible_patents: int = 25
    score_threshold: float = 0.68
    samples_per_region: int = 3
    min_hit_rate_for_sft: float = 0.5

    @classmethod
    def development(cls) -> MaskingConfig:
        """Smaller thresholds when the corpus is not fully bulk-indexed yet."""
        return cls(
            min_region_size=8,
            min_visible_patents=3,
            n_hidden_min=2,
            n_hidden_max=5,
            samples_per_region=2,
        )

    @classmethod
    def from_env(cls) -> MaskingConfig:
        if os.getenv("MASKING_DEV_MODE", "").lower() in ("1", "true", "yes"):
            return cls.development()
        return cls()
