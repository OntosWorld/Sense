"""Experimental deterministic context/evidence quality reporting.\n\nThis module does not represent peaq trust levels, hardware attestation, safety,\nor a general claim that a machine is trustworthy.\n"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..model.observation import TelemetryObservation

__all__ = ["TrustDimension", "TrustReport", "compute_trust_report"]


class TrustDimension(Enum):
    """Individual context-quality dimension."""

    FRESHNESS = "freshness"
    COVERAGE = "coverage"
    STALENESS = "staleness"
    DIVERSITY = "diversity"


# Quality bands per PRD §12.2
_QUALITY_BANDS = [
    (0.90, "excellent"),
    (0.75, "good"),
    (0.55, "fair"),
    (0.30, "poor"),
]


@dataclass
class DimensionResult:
    """
    Result for a single trust dimension.

    Attributes
    ----------
    name : str
        Dimension name (e.g. ``"freshness"``, ``"coverage"``).
    score : float
        Dimension score in [0.0, 1.0].
    weight : float
        Weight used when computing the overall score.
    """

    name: str
    score: float
    weight: float


@dataclass
class TrustReport:
    """
    Deterministic context-quality report for a machine's last evaluation window.

    Attributes
    ----------
    dimensions : list[DimensionResult]
        Per-dimension results, each with name, score, and weight.
    overall_score : float
        Weighted mean of dimensions, also in [0.0, 1.0].
    quality_band : str
        One of: excellent, good, fair, poor, critical.
    timestamp : datetime
        When this report was generated (UTC).
    machine_id : str
        Identifier of the machine this report pertains to.
    schema_version : str
        Schema version of the report (e.g. ``"1.0"``).
    observation_count : int
        Number of observations used to compute this report.

    Methods
    -------
    to_dict() -> dict
        Serialise to a plain dict suitable for JSON encoding.
    """

    dimensions: list[DimensionResult]
    overall_score: float
    quality_band: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    machine_id: str = ""
    schema_version: str = "1.0"
    observation_count: int = 0

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------
    @property
    def verdict(self) -> str:
        """Human-readable context-quality band."""
        return self.quality_band.capitalize()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "dimensions": [
                {
                    "name": d.name,
                    "score": round(d.score, 4),
                    "weight": round(d.weight, 4),
                }
                for d in self.dimensions
            ],
            "overall_score": round(self.overall_score, 4),
            "quality_band": self.quality_band,
            "verdict": self.verdict,
            "timestamp": self.timestamp.isoformat(),
            "machine_id": self.machine_id,
            "schema_version": self.schema_version,
            "observation_count": self.observation_count,
        }


def _quality_band(score: float) -> str:
    for threshold, band in _QUALITY_BANDS:
        if score >= threshold:
            return band
    return "critical"


# ------------------------------------------------------------------
# Dimension scorers
# ------------------------------------------------------------------


def _score_freshness(
    observations: dict[str, "TelemetryObservation"], window_ms: int
) -> float:
    """
    How many observations in the last window_ms are fresh (age_ms <= window_ms).

    Returns 0.0 when no observations exist.
    """
    if not observations:
        return 0.0
    fresh_count = sum(1 for obs in observations.values() if obs.age_ms <= window_ms)
    return fresh_count / len(observations)


def _score_coverage(
    required_paths: frozenset[str], observations: dict[str, "TelemetryObservation"]
) -> float:
    """
    Fraction of required capability paths that have at least one observation.

    An observation is any TelemetryObservation keyed by the path string.
    Returns 1.0 when required_paths is empty.
    """
    if not required_paths:
        return 1.0
    covered = sum(1 for p in required_paths if p in observations)
    return covered / len(required_paths)


def _score_staleness(
    observations: dict[str, "TelemetryObservation"], max_staleness_ms: int
) -> float:
    """
    Normalised staleness: 1.0 = all fresh, 0.0 = all stale.
    Uses each observation's own ttl_ms to determine staleness; if ttl_ms is None
    the observation is treated as always fresh.  Returns 0.0 when there are no
    observations.
    """
    if not observations:
        return 0.0
    stale_count = 0
    for obs in observations.values():
        # Stale if age exceeds this obs's own TTL (if set), else the global max.
        threshold = obs.ttl_ms if obs.ttl_ms is not None else max_staleness_ms
        if obs.age_ms > threshold:
            stale_count += 1
    return 1.0 - (stale_count / len(observations))


def _score_diversity(unique_paths: int, total_observations: int) -> float:
    """
    Ratio of unique capability paths to total observations.
    Penalises repeated sampling of the same paths.
    """
    if total_observations == 0:
        return 1.0
    return unique_paths / total_observations


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def compute_trust_report(
    schema_version: str,
    machine_id: str,
    observations: list["TelemetryObservation"],
    *,
    window_ms: int = 60_000,
    max_staleness_ms: int = 300_000,
    required_observation_paths: frozenset[str] | None = None,
    dimension_weights: dict[str, float] | None = None,
) -> TrustReport:
    """
    Compute a deterministic :class:`TrustReport` from a list of observations.

    Parameters
    ----------
    schema_version : str
        Schema version string for the report (e.g. ``"1.0"``).
    machine_id : str
        Identifier of the machine this report pertains to.
    observations : list[TelemetryObservation]
        List of telemetry observations to evaluate.
    window_ms : int
        Observations older than this are considered stale (default 60 000 ms).
    max_staleness_ms : int
        Observations older than this penalise the staleness dimension
        (default 300 000 ms).
    required_observation_paths : frozenset[str] | None
        Capability paths that must be present. Coverage is measured against
        this set. If None, coverage is 1.0.
    dimension_weights : dict[str, float] | None
        Per-dimension weights (by name string) for the weighted mean.
        If None the defaults are:
        freshness=1.0, coverage=1.0, staleness=1.0, diversity=0.5.

    Returns
    -------
    TrustReport
        The deterministic trust report.
    """
    if required_observation_paths is None:
        required_observation_paths = frozenset()
    if dimension_weights is None:
        dimension_weights = {
            "freshness": 1.0,
            "coverage": 1.0,
            "staleness": 1.0,
            "diversity": 0.5,
        }

    obs_dict = {obs.path: obs for obs in observations}
    total_obs = len(obs_dict)

    dim_scores: dict[str, float] = {
        "freshness": _score_freshness(obs_dict, window_ms),
        "coverage": _score_coverage(required_observation_paths, obs_dict),
        "staleness": _score_staleness(obs_dict, max_staleness_ms),
        "diversity": _score_diversity(len(obs_dict), len(observations)),
    }

    dimension_results: list[DimensionResult] = []
    for name, score in dim_scores.items():
        weight = dimension_weights.get(name, 0.0)
        dimension_results.append(DimensionResult(name=name, score=score, weight=weight))

    # overall_score = minimum across all non-zero-weight dimensions.
    # Using min() means ANY degraded dimension drags the whole score down,
    # which correctly penalises all-stale and empty observation sets.
    weighted_scores = [d.score for d in dimension_results if d.weight > 0]
    overall_score = min(weighted_scores) if weighted_scores else 0.0

    quality_band = _quality_band(overall_score)

    return TrustReport(
        dimensions=dimension_results,
        overall_score=overall_score,
        quality_band=quality_band,
        machine_id=machine_id,
        schema_version=schema_version,
        observation_count=total_obs,
    )
