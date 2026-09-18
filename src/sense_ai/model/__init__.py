"""Public Sense domain model types.

ContextMachine is imported lazily so the telemetry normalization package can use
observation types without creating a package-import cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .capability import CapabilitySpec, capability
from .observation import TelemetryObservation
from .result import (
    CapabilityResult,
    CapabilityStatus,
    ConstraintResult,
    ContextTransition,
)
from .snapshot import CapabilitySnapshot, ContextSnapshot

if TYPE_CHECKING:
    from .machine import ContextMachine

__all__ = [
    "TelemetryObservation",
    "ContextMachine",
    "CapabilitySpec",
    "capability",
    "CapabilityResult",
    "CapabilityStatus",
    "ConstraintResult",
    "ContextTransition",
    "CapabilitySnapshot",
    "ContextSnapshot",
]


def __getattr__(name: str) -> Any:
    if name == "ContextMachine":
        from .machine import ContextMachine

        return ContextMachine
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
