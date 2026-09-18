"""Result types — CapabilityStatus, ConstraintResult, Transition — per PRD §9."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CapabilityStatus(str, Enum):
    """
    v1 capability status values, per PRD §9.4.

    Consumers MUST NOT treat ``UNKNOWN`` as ``AVAILABLE``.
    """

    AVAILABLE = "AVAILABLE"
    """All required evidence exists, is fresh, and all mandatory constraints pass."""

    DEGRADED = "DEGRADED"
    """
    Mandatory constraints still permit operation, but one or more
    developer-defined warning/degradation rules are active.
    """

    UNAVAILABLE = "UNAVAILABLE"
    """At least one mandatory rule fails (equality, comparison, or staleness)."""

    UNKNOWN = "UNKNOWN"
    """
    Required evidence is absent, invalid, or too stale to evaluate safely.
    ``UNKNOWN`` MUST NOT be treated as ``AVAILABLE``.
    """


@dataclass
class ConstraintResult:
    """
    Explanation of a single rule outcome, per PRD §9.5.

    Attributes
    ----------
    code : str
        Machine-readable identifier for this outcome, e.g. ``"LOCALIZATION_STALE"``.
    severity : Literal["blocking", "warning"]
        ``"blocking"`` — mandatory constraint; causes ``UNAVAILABLE`` if violated.
        ``"warning"`` — optional degrade rule; causes ``DEGRADED`` if violated.
    path : str
        The observation path this constraint evaluated.
    expected : str
        Human-readable description of what was expected.
    observed : Any
        The actual observed value, or ``None`` if the path was absent.
    observed_age_ms : int | None
        Age of the observation at evaluation time, in milliseconds.
        ``None`` when the path was absent or timing is not applicable.
    constraint_name : str | None
        Optional name of the rule that produced this result.
    """

    code: str
    severity: str  # Literal["blocking", "warning"]
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
        }


@dataclass
class CapabilityResult:
    """
    Outcome of evaluating one named capability, per PRD §9.4 / §9.5.

    Attributes
    ----------
    name : str
        Capability name, e.g. ``"warehouse.pick"``.
    status : CapabilityStatus
        The overall status after evaluating all constraints.
    blocking : list[ConstraintResult]
        Constraints with ``severity == "blocking"`` that failed.
        Empty when status is ``AVAILABLE``, ``DEGRADED``, or ``UNKNOWN``.
    warnings : list[ConstraintResult]
        Constraints with ``severity == "warning"`` that failed.
        Non-empty when status is ``DEGRADED``.
    unknown_paths : list[str]
        Observation paths that were required but absent or too stale to evaluate.
    evaluated_at : datetime
        Timestamp of evaluation (UTC).
    """

    name: str
    status: CapabilityStatus
    blocking: list[ConstraintResult] = field(default_factory=list)
    warnings: list[ConstraintResult] = field(default_factory=list)
    unknown_paths: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    python_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "blocking": [r.to_dict() for r in self.blocking],
            "warnings": [r.to_dict() for r in self.warnings],
            "unknown_paths": self.unknown_paths,
            "evaluated_at": self.evaluated_at.isoformat(),
            "python_warnings": self.python_warnings,
        }


@dataclass
class ContextTransition:
    """
    A detected capability-state change, per PRD §9.6.

    A transition occurs when a capability's status changes between evaluations.
    """

    capability: str
    current: CapabilityStatus
    previous: CapabilityStatus | None = None  # None means first evaluation / UNKNOWN
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    snapshot_ref: str | None = None  # Optional reference to the generating snapshot

    @property
    def label(self) -> str:
        prev = self.previous.value if self.previous else "NONE"
        return f"{prev} → {self.current.value}"
