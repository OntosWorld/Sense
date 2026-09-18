"""Sense model package — per PRD §9 domain types."""

from __future__ import annotations

from .capability import CapabilitySpec, capability
from .machine import ContextMachine
from .observation import TelemetryObservation
from .result import (
    CapabilityResult,
    CapabilityStatus,
    ConstraintResult,
    ContextTransition,
)
from .snapshot import CapabilitySnapshot, ContextSnapshot

__all__ = [
    # Observation
    "TelemetryObservation",
    # Machine
    "ContextMachine",
    # Capability
    "CapabilitySpec",
    "capability",
    # Result types
    "CapabilityResult",
    "CapabilityStatus",
    "ConstraintResult",
    "ContextTransition",
    # Snapshot
    "CapabilitySnapshot",
    "ContextSnapshot",
]
