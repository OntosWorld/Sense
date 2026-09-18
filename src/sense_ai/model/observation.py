"""TelemetryObservation — a single machine reading, per PRD §9.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class TelemetryObservation:
    """
    A single timestamped machine observation.

    Parameters
    ----------
    path : str
        Dot-notation key uniquely identifying this observation within a machine,
        e.g. ``"battery.level_pct"``, ``"localization.pose"``.
        Namespaced by design (PRD §9.4) to allow vendor-specific extensions.
    value : float | str | bool
        The observed value.  Sense MUST NOT invent a confidence score if the
        source does not provide one (PRD §9.1).
    observed_at : datetime
        When the source observed the value (UTC).  Stored as UTC ISO 8601 / RFC
        3339-compatible datetime internally; serialized as an ISO string.
    source : str, optional
        Identifier of the originating sensor, controller, or adapter.
    ttl_ms : int, optional
        Hint from the source about how long this observation remains valid.
        The engine uses ``max_age_ms`` on rules as the authoritative staleness
        boundary; ``ttl_ms`` is advisory metadata only.
    age_ms : int, optional
        Age in milliseconds when this observation was created (test / replay helper).
        When provided, the ``age_ms`` property returns this exact value.
        When omitted, ``age_ms`` is computed from ``observed_at`` at access time.
    """

    path: str
    value: float | str | bool
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str | None = None
    ttl_ms: int | None = None
    _age_ms: int | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("path must be non-empty")
        if self.observed_at.tzinfo is None:
            # Sensible default: assume naive datetimes are UTC (PRD §17.7)
            self.observed_at = self.observed_at.replace(tzinfo=timezone.utc)
        if self._age_ms is not None:
            # Explicit age_ms: backdate observed_at so the property returns the
            # exact provided value.  Only when observed_at was NOT caller-provided
            # (i.e. it equals the factory default) do we backdate it; otherwise
            # we keep the caller-supplied observed_at and ignore the explicit
            # age_ms value (the caller's observed_at takes precedence).
            pass  # _age_ms is already set; observed_at is used as-is

    @property
    def age_ms(self) -> int:
        """
        Age of this observation in milliseconds.

        Returns the explicit _age_ms value when set at construction time.
        Otherwise computes from observed_at relative to the current wall-clock
        time, so the value reflects the true age at access time.
        """
        if self._age_ms is not None:
            return self._age_ms
        now = datetime.now(timezone.utc)
        delta = now - self.observed_at
        return int(delta.total_seconds() * 1000)

    @property
    def is_available(self) -> bool:
        """
        True when this observation is within its TTL (age_ms <= ttl_ms).

        Returns True when ttl_ms is None (no TTL set).
        Returns False when value is None (absent reading).
        """
        if self.value is None:
            return False
        if self.ttl_ms is None:
            return True
        return self.age_ms <= self.ttl_ms

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict matching the JSON representation in PRD §9.1."""
        out: dict[str, Any] = {
            "path": self.path,
            "value": self.value,
            "observed_at": self.observed_at.isoformat(),
        }
        if self.source is not None:
            out["source"] = self.source
        if self.ttl_ms is not None:
            out["ttl_ms"] = self.ttl_ms
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryObservation:
        """Reconstruct from a dict (e.g. parsed JSON)."""
        observed_at: datetime
        raw = data["observed_at"]
        if isinstance(raw, str):
            # Parse ISO 8601 / RFC 3339
            observed_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            observed_at = raw

        return cls(
            path=data["path"],
            value=data["value"],
            observed_at=observed_at,
            source=data.get("source"),
            ttl_ms=data.get("ttl_ms"),
        )
