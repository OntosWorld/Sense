"""TelemetryObservation — a single machine reading, per PRD §9.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TypeAlias

JsonValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
    | list["JsonValue"]
    | dict[str, "JsonValue"]
)


@dataclass
class TelemetryObservation:
    """
    A single timestamped machine observation.

    observed_at records when the source measured the value. received_at
    records when Sense received it. Those timestamps are intentionally kept
    separate so transport delay is not hidden.

    ttl_ms is the maximum lifetime of the observation itself. Capability
    rules may impose a stricter freshness limit with fresh(...).
    """

    path: str
    value: JsonValue
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str | None = None
    ttl_ms: int | None = None
    _age_ms: int | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("path must be non-empty")
        if self.observed_at.tzinfo is None:
            self.observed_at = self.observed_at.replace(tzinfo=timezone.utc)
        if self.received_at.tzinfo is None:
            self.received_at = self.received_at.replace(tzinfo=timezone.utc)
        if self.ttl_ms is not None and self.ttl_ms < 0:
            raise ValueError("ttl_ms must be >= 0 when provided")

    @property
    def age_ms(self) -> int:
        """Age since the source observation time, in milliseconds."""
        if self._age_ms is not None:
            return self._age_ms
        now = datetime.now(timezone.utc)
        delta = now - self.observed_at
        return max(0, int(delta.total_seconds() * 1000))

    @property
    def transport_delay_ms(self) -> int:
        """Delay between source observation and receipt by Sense."""
        delta = self.received_at - self.observed_at
        return max(0, int(delta.total_seconds() * 1000))

    @property
    def is_available(self) -> bool:
        """
        Whether the observation is still valid under its own TTL.

        ttl_ms=None means the source supplied no expiry. A JSON null value is
        still a valid observation; whether it is useful is determined by the
        capability rule evaluating it.
        """
        if self.ttl_ms is None:
            return True
        return self.age_ms <= self.ttl_ms

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the language-neutral Sense context representation."""
        out: dict[str, Any] = {
            "path": self.path,
            "value": self.value,
            "observed_at": self.observed_at.isoformat(),
            "received_at": self.received_at.isoformat(),
        }
        if self.source is not None:
            out["source"] = self.source
        if self.ttl_ms is not None:
            out["ttl_ms"] = self.ttl_ms
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryObservation:
        """Reconstruct an observation from serialized context data."""

        def _parse_time(value: Any, field_name: str) -> datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            raise TypeError(f"{field_name} must be an ISO 8601 string or datetime")

        observed_at = _parse_time(data["observed_at"], "observed_at")
        received_raw = data.get("received_at", data["observed_at"])
        received_at = _parse_time(received_raw, "received_at")

        return cls(
            path=data["path"],
            value=data.get("value"),
            observed_at=observed_at,
            received_at=received_at,
            source=data.get("source"),
            ttl_ms=data.get("ttl_ms"),
        )
