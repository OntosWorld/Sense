"""
Deterministic trust evaluation framework (FR-12, FR-13).

Provides a ``TrustReport`` that summarises how trustworthy a machine's
``ContextSnapshot`` is — based solely on signal quality, staleness, and
diversity metrics computed from the observations themselves.

All computations are deterministic and require no external services or AI
models (per FR-5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

from sense_ai.model import TelemetryObservation

# ----------------------------------------------------------------------
# Trust dimensions
# ----------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class TrustDimension:
    """
    One axis of trust measurement.

    Attributes:
        name: Identifier for this dimension (e.g. ``"freshness"``).
        score: Normalised score in the interval [0.0, 1.0].
            1.0 = fully trusted, 0.0 = fully untrusted.
        weight: Relative importance when computing the overall trust score.
            Weights are normalised internally; the sum need not be 1.0.
    """

    name: str
    score: float
    weight: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0.0, 1.0], got {self.score!r}")
        if self.weight < 0.0:
            raise ValueError(f"weight must be non-negative, got {self.weight!r}")


@dataclass(frozen=True)
class TrustReport:
    """
    Complete trust assessment for a ``ContextSnapshot``.

    Produced by ``compute_trust_report``.  All fields are derived deterministically
    from the input observations.

    Attributes:
        schema_version: Snapshot schema version this report was computed for.
        machine_id: Machine this report applies to.
        dimensions: Per-axis trust scores.
        overall_score: Weighted mean of ``dimensions``; in [0.0, 1.0].
        quality_band: Human-readable quality tier.
        observation_count: Number of observations factored into the assessment.
        computed_at_iso: ISO 8601 timestamp of computation.
    """

    schema_version: str
    machine_id: str
    dimensions: tuple[TrustDimension, ...] = field(default_factory=tuple)
    overall_score: float = 0.0
    quality_band: str = "unknown"
    observation_count: int = 0
    computed_at_iso: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "machine_id": self.machine_id,
            "overall_score": round(self.overall_score, 4),
            "quality_band": self.quality_band,
            "observation_count": self.observation_count,
            "computed_at_iso": self.computed_at_iso,
            "dimensions": [
                {"name": d.name, "score": round(d.score, 4), "weight": d.weight}
                for d in self.dimensions
            ],
        }


# ----------------------------------------------------------------------
# Band thresholds
# ----------------------------------------------------------------------

_BANDS = (
    (0.90, "excellent"),
    (0.75, "good"),
    (0.55, "fair"),
    (0.30, "poor"),
    (0.00, "critical"),
)


def _classify(score: float) -> str:
    for threshold, label in _BANDS:
        if score >= threshold:
            return label
    return "critical"


# ----------------------------------------------------------------------
# Dimension calculators
# ----------------------------------------------------------------------


def _freshness_score(observations: Sequence[TelemetryObservation]) -> float:
    """
    Fraction of observations that are within their TTL.

    A missing observation (value is None) counts as 0.
    """
    if not observations:
        return 0.0
    fresh = sum(
        1.0
        for obs in observations
        if obs.value is not None and obs.age_ms is not None and obs.age_ms <= obs.ttl_ms
    )
    return fresh / len(observations)


def _coverage_score(
    observations: Sequence[TelemetryObservation],
    required_paths: frozenset[str] | None = None,
) -> float:
    """
    Fraction of *required paths* that have a non-null observation.

    If ``required_paths`` is None, uses all observed paths (i.e. every path
    that appears is trivially "covered" by itself — this gives a score of 1.0
    unless there are zero observations at all).
    """
    if not observations:
        return 0.0
    if required_paths is None:
        return 1.0
    covered = {obs.path for obs in observations if obs.value is not None}
    return len(covered & required_paths) / len(required_paths)


def _staleness_score(observations: Sequence[TelemetryObservation]) -> float:
    """
    Average normalised age across all observations.

    Normalised age = min(age_ms / ttl_ms, 1.0).
    An observation with ttl_ms == 0 is treated as permanently stale (1.0).
    """
    if not observations:
        return 1.0  # no data = maximally stale

    total_normalised = 0.0
    for obs in observations:
        if obs.age_ms is None or obs.ttl_ms <= 0:
            norm = 1.0
        else:
            norm = min(obs.age_ms / obs.ttl_ms, 1.0)
        total_normalised += norm

    # Invert: low normalised age = high staleness score
    avg_norm = total_normalised / len(observations)
    return 1.0 - avg_norm


def _diversity_score(observations: Sequence[TelemetryObservation]) -> float:
    """
    Ratio of unique observed paths to total observation count.

    High diversity (many unique paths) is slightly favoured as it indicates
    a well-instrumented machine.  Capped at 1.0.
    """
    if not observations:
        return 0.0
    unique_paths = {obs.path for obs in observations}
    return min(len(unique_paths) / max(len(observations), 1), 1.0)


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def compute_trust_report(
    schema_version: str,
    machine_id: str,
    observations: Sequence[TelemetryObservation],
    required_observation_paths: frozenset[str] | None = None,
    computed_at_iso: str = "",
    dimension_weights: dict[str, float] | None = None,
) -> TrustReport:
    """
    Compute a deterministic ``TrustReport`` from ``observations``.

    Dimensions computed:

    1. **freshness** – how many observations are within their TTL.
    2. **coverage**  – how many required paths have a non-null value.
    3. **staleness** – average how stale (relative to TTL) the observations are.
    4. **diversity** – ratio of unique paths to total observations.

    The ``overall_score`` is the weighted mean of the four dimensions.
    Weights can be overridden via ``dimension_weights``; unknown keys are
    ignored and use the default weight of 1.0.

    Args:
        schema_version: Snapshot schema version string.
        machine_id: Identifier of the machine.
        observations: All telemetry observations in the snapshot.
        required_observation_paths: Paths that *must* be present for full coverage.
            If None, coverage is measured against all observed paths (always 1.0 unless empty).
        computed_at_iso: ISO 8601 timestamp to embed in the report. If empty, the
            current UTC time is used.
        dimension_weights: Override default dimension weights, e.g.
            ``{"freshness": 2.0, "staleness": 0.5}``.

    Returns:
        A ``TrustReport`` with all dimensions and the overall score.
    """
    from datetime import datetime, timezone

    if not computed_at_iso:
        computed_at_iso = datetime.now(timezone.utc).isoformat()

    defaults: dict[str, float] = {
        "freshness": 1.0,
        "coverage": 1.0,
        "staleness": 1.0,
        "diversity": 0.5,  # diversity is less critical
    }
    if dimension_weights:
        defaults.update(dimension_weights)

    freshness = _freshness_score(observations)
    coverage = _coverage_score(observations, required_observation_paths)
    staleness = _staleness_score(observations)
    diversity = _diversity_score(observations)

    raw_dims: list[TrustDimension] = [
        TrustDimension("freshness", freshness, defaults["freshness"]),
        TrustDimension("coverage", coverage, defaults["coverage"]),
        TrustDimension("staleness", staleness, defaults["staleness"]),
        TrustDimension("diversity", diversity, defaults["diversity"]),
    ]

    total_weight = sum(d.weight for d in raw_dims)
    overall = (
        sum(d.score * d.weight for d in raw_dims) / total_weight
        if total_weight > 0
        else 0.0
    )

    return TrustReport(
        schema_version=schema_version,
        machine_id=machine_id,
        dimensions=tuple(sorted(raw_dims, key=lambda d: d.name)),
        overall_score=overall,
        quality_band=_classify(overall),
        observation_count=len(observations),
        computed_at_iso=computed_at_iso,
    )
