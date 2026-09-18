"""Result types for capability evaluation and state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CapabilityStatus(str, Enum):
    """Current usability of a machine capability."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class ConstraintResult:
    """Explanation of one evaluated constraint."""

    code: str
    severity: str
    path: str
    expected: str
    observed: Any
    observed_age_ms: int | None = None
    constraint_name: str | None = None
    is_absent: bool = False
    is_stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "path": self.path,
            "expected": self.expected,
            "observed": self.observed,
            "observed_age_ms": self.observed_age_ms,
            "constraint_name": self.constraint_name,
            "is_absent": self.is_absent,
            "is_stale": self.is_stale,
        }


@dataclass(slots=True)
class CapabilityResult:
    """Outcome of evaluating one named capability."""

    name: str = ""
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    blocking: list[ConstraintResult] = field(default_factory=list)
    warnings: list[ConstraintResult] = field(default_factory=list)
    unknown_paths: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    python_warnings: list[str] = field(default_factory=list)

    @property
    def reasons(self) -> list[ConstraintResult]:
        """All blocking and warning reasons in evaluation order."""
        return [*self.blocking, *self.warnings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "blocking": [result.to_dict() for result in self.blocking],
            "warnings": [result.to_dict() for result in self.warnings],
            "unknown_paths": list(self.unknown_paths),
            "evaluated_at": self.evaluated_at.isoformat(),
            "python_warnings": list(self.python_warnings),
        }


@dataclass(slots=True)
class ContextTransition:
    """A meaningful change in one capability's evaluated status."""

    capability: str = ""
    current: CapabilityStatus = CapabilityStatus.UNKNOWN
    previous: CapabilityStatus | None = None
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    snapshot_ref: str | None = None
    reasons: list[dict[str, Any]] = field(default_factory=list)

    @property
    def label(self) -> str:
        previous = self.previous.value if self.previous is not None else "NONE"
        return f"{previous} → {self.current.value}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "previous": self.previous.value if self.previous is not None else None,
            "current": self.current.value,
            "at": self.at.isoformat(),
            "snapshot_ref": self.snapshot_ref,
            "reasons": list(self.reasons),
        }
