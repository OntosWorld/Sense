"""Result types for capability evaluation and state transitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sense_ai.rules import ConstraintOutcome


class CapabilityStatus(str, Enum):
    """Current usability of a machine capability."""

    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(slots=True)
class ConstraintResult:
    """Explanation of one evaluated constraint, including composed children."""

    code: str
    severity: str
    path: str
    expected: str
    observed: Any
    observed_age_ms: int | None = None
    constraint_name: str | None = None
    is_absent: bool = False
    is_stale: bool = False
    is_invalid: bool = False
    children: list[ConstraintResult] = field(default_factory=list)

    @property
    def is_unknown(self) -> bool:
        return self.is_absent or self.is_stale or self.is_invalid

    @classmethod
    def from_outcome(
        cls,
        outcome: ConstraintOutcome,
        *,
        severity: str,
    ) -> ConstraintResult:
        return cls(
            code=outcome.code,
            severity=severity,
            path=outcome.path,
            expected=outcome.expected,
            observed=outcome.observed,
            observed_age_ms=outcome.age_ms,
            constraint_name=outcome.constraint_name,
            is_absent=outcome.is_absent,
            is_stale=outcome.is_stale,
            is_invalid=outcome.is_invalid,
            children=[cls.from_outcome(child, severity=severity) for child in outcome.children],
        )

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
            "is_invalid": self.is_invalid,
            "children": [child.to_dict() for child in self.children],
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

    def to_dict(self, *, include_observed_values: bool = True) -> dict[str, Any]:
        return {
            "capability": self.capability,
            "previous": self.previous.value if self.previous is not None else None,
            "current": self.current.value,
            "at": self.at.isoformat(),
            "snapshot_ref": self.snapshot_ref,
            "reasons": [
                _serialize_reason(
                    reason,
                    include_observed_values=include_observed_values,
                )
                for reason in self.reasons
            ],
        }


def _serialize_reason(
    reason: dict[str, Any],
    *,
    include_observed_values: bool,
) -> dict[str, Any]:
    serialized = dict(reason)
    if not include_observed_values:
        serialized.pop("observed", None)
    raw_children = serialized.get("children", [])
    if isinstance(raw_children, list):
        serialized["children"] = [
            _serialize_reason(
                child,
                include_observed_values=include_observed_values,
            )
            for child in raw_children
            if isinstance(child, dict)
        ]
    return serialized
