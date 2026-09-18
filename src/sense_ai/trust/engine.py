"""Evidence-quality scoring for Sense machine context.

This module does not determine whether a machine is trustworthy and does not
represent peaq event trust levels. It only summarizes the quality of the local
telemetry evidence available to Sense.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from sense_ai.model.observation import TelemetryObservation


class EvidenceQualityDimension(str, Enum):
    FRESHNESS = "freshness"
    COVERAGE = "coverage"
    STALENESS = "staleness"
    DIVERSITY = "diversity"


@dataclass(frozen=True, slots=True)
class DimensionResult:
    name: str
    score: float
    weight: float


@dataclass(frozen=True, slots=True)
class EvidenceQualityReport:
    """Deterministic quality summary of the evidence in a Sense snapshot."""

    dimensions: tuple[DimensionResult, ...]
    overall_score: float
    quality_band: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    machine_id: str = ""
    schema_version: str = "1.0"
    observation_count: int = 0

    @property
    def verdict(self) -> str:
        return self.quality_band.capitalize()

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": [
                {
                    "name": dimension.name,
                    "score": round(dimension.score, 4),
                    "weight": round(dimension.weight, 4),
                }
                for dimension in self.dimensions
            ],
            "overall_score": round(self.overall_score, 4),
            "quality_band": self.quality_band,
            "timestamp": self.timestamp.isoformat(),
            "machine_id": self.machine_id,
            "schema_version": self.schema_version,
            "observation_count": self.observation_count,
        }


_QUALITY_BANDS = (
    (0.90, "excellent"),
    (0.75, "good"),
    (0.55, "fair"),
    (0.30, "poor"),
    (0.00, "critical"),
)


def _quality_band(score: float) -> str:
    for threshold, band in _QUALITY_BANDS:
        if score >= threshold:
            return band
    return "critical"


def _freshness(
    observations: dict[str, TelemetryObservation],
    window_ms: int,
) -> float:
    if not observations:
        return 0.0
    fresh = sum(
        1
        for observation in observations.values()
        if observation.age_ms
        <= (
            min(window_ms, observation.ttl_ms)
            if observation.ttl_ms is not None
            else window_ms
        )
    )
    return fresh / len(observations)


def _coverage(
    observations: dict[str, TelemetryObservation],
    required_paths: frozenset[str],
) -> float:
    if not required_paths:
        return 1.0 if observations else 0.0
    available = {
        path
        for path, observation in observations.items()
        if observation.value is not None and observation.is_available
    }
    return len(available & required_paths) / len(required_paths)


def _staleness(
    observations: dict[str, TelemetryObservation],
    max_staleness_ms: int,
) -> float:
    if not observations:
        return 0.0
    fresh = 0
    for observation in observations.values():
        threshold = (
            observation.ttl_ms
            if observation.ttl_ms is not None
            else max_staleness_ms
        )
        if observation.age_ms <= threshold:
            fresh += 1
    return fresh / len(observations)


def _diversity(
    observations: list[TelemetryObservation],
) -> float:
    if not observations:
        return 0.0
    return len({observation.path for observation in observations}) / len(observations)


def compute_evidence_quality(
    schema_version: str,
    machine_id: str,
    observations: list[TelemetryObservation],
    *,
    window_ms: int = 60_000,
    max_staleness_ms: int = 300_000,
    required_observation_paths: frozenset[str] | None = None,
    dimension_weights: dict[str, float] | None = None,
) -> EvidenceQualityReport:
    """Compute evidence quality from local observations only."""
    required_paths = required_observation_paths or frozenset()
    weights = {
        "freshness": 1.0,
        "coverage": 1.0,
        "staleness": 1.0,
        "diversity": 0.5,
    }
    if dimension_weights:
        weights.update(dimension_weights)

    by_path = {observation.path: observation for observation in observations}
    scores = {
        "freshness": _freshness(by_path, window_ms),
        "coverage": _coverage(by_path, required_paths),
        "staleness": _staleness(by_path, max_staleness_ms),
        "diversity": _diversity(observations),
    }
    dimensions = tuple(
        DimensionResult(name=name, score=score, weight=weights.get(name, 0.0))
        for name, score in scores.items()
    )
    weighted = [item.score for item in dimensions if item.weight > 0]
    overall = min(weighted) if weighted else 0.0

    return EvidenceQualityReport(
        dimensions=dimensions,
        overall_score=overall,
        quality_band=_quality_band(overall),
        machine_id=machine_id,
        schema_version=schema_version,
        observation_count=len(observations),
    )


# Compatibility aliases. New documentation uses "evidence quality" to avoid
# colliding with peaq's protocol-level trust levels.
TrustDimension = EvidenceQualityDimension
TrustReport = EvidenceQualityReport
compute_trust_report = compute_evidence_quality
