"""Telemetry observation model used by the Sense context engine."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TypeAlias

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

_PATH_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass(slots=True)
class TelemetryObservation:
    """A single timestamped machine observation.

    observed_at records when the source measured the value.
    received_at records when Sense received it. They are intentionally
    separate because transport delay can matter for physical systems.

    ttl_ms is source-provided validity metadata. Capability-specific freshness
    requirements should still be declared explicitly with sense_ai.fresh().
    """

    path: str
    value: JSONValue
    observed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    received_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: str | None = None
    ttl_ms: int | None = None
    _age_ms: int | None = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not _PATH_RE.fullmatch(self.path):
            raise ValueError(
                "path must be dot-separated identifiers, e.g. 'battery.level_pct'"
            )
        self.observed_at = _utc(self.observed_at)
        self.received_at = _utc(self.received_at)
        if self.ttl_ms is not None and self.ttl_ms < 0:
            raise ValueError("ttl_ms must be >= 0 when provided")
        if self._age_ms is not None and self._age_ms < 0:
            raise ValueError("_age_ms must be >= 0 when provided")

    @property
    def age_ms(self) -> int:
        """Age of the source observation in milliseconds."""
        if self._age_ms is not None:
            return self._age_ms
        delta = datetime.now(timezone.utc) - self.observed_at
        return max(0, int(delta.total_seconds() * 1000))

    @property
    def receive_delay_ms(self) -> int:
        """Delay between source observation and receipt by Sense."""
        delta = self.received_at - self.observed_at
        return max(0, int(delta.total_seconds() * 1000))

    @property
    def is_available(self) -> bool:
        """Whether the observation is present and inside its declared TTL."""
        if self.value is None:
            return False
        if self.ttl_ms is None:
            return True
        return self.age_ms <= self.ttl_ms

    def to_dict(self) -> dict[str, JSONValue]:
        """Serialize to the language-neutral Sense context shape."""
        out: dict[str, JSONValue] = {
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
    def from_dict(cls, data: dict[str, JSONValue]) -> "TelemetryObservation":
        """Reconstruct an observation from its serialized representation."""
        raw_observed = data["observed_at"]
        if not isinstance(raw_observed, str):
            raise ValueError("observed_at must be an ISO 8601 string")
        observed_at = datetime.fromisoformat(raw_observed.replace("Z", "+00:00"))

        raw_received = data.get("received_at")
        if raw_received is None:
            received_at = observed_at
        elif isinstance(raw_received, str):
            received_at = datetime.fromisoformat(raw_received.replace("Z", "+00:00"))
        else:
            raise ValueError("received_at must be an ISO 8601 string when provided")

        path = data["path"]
        if not isinstance(path, str):
            raise ValueError("path must be a string")

        source = data.get("source")
        if source is not None and not isinstance(source, str):
            raise ValueError("source must be a string when provided")

        ttl = data.get("ttl_ms")
        if ttl is not None and (not isinstance(ttl, int) or isinstance(ttl, bool)):
            raise ValueError("ttl_ms must be an integer when provided")

        return cls(
            path=path,
            value=data.get("value"),
            observed_at=observed_at,
            received_at=received_at,
            source=source,
            ttl_ms=ttl,
        )
