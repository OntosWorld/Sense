"""
Sense — Contextual evaluation framework for physical AI and robotics.

Top-level public API, per PRD §11.1.

Quick start::

    from Sense import ContextMachine, capability
    from sense_ai.rules import equals, gte, fresh

    machine = ContextMachine(machine_ref="robot-001")
    machine.define_capability(
        capability(
            "warehouse.pick",
            requires=[
                equals("tool.gripper.available", True),
                gte("battery.level_pct", 20),
                fresh("localization.pose", max_age_ms=1000),
            ],
            degrade_when=[
                gte("payload.utilization_pct", 90),
            ],
        )
    )
    machine.observe("battery.level_pct", 34)
    result = machine.evaluate("warehouse.pick")
    print(result.status)  # AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
"""

from __future__ import annotations

# Typed errors (FR-14)
from sense_ai.errors import (
    InvalidRuleError,
    MissingEvidenceError,
    PeaqConfigurationError,
    PeaqNetworkError,
    SchemaValidationError,
    SenseError,
    SerializationError,
    UnknownCapabilityError,
    UnsupportedPeaqFlowError,
)

# Events (FR-7)
from sense_ai.events import (
    CapabilityEvaluatedEvent,
    EventBus,
    EventHandler,
    EventType,
    RawEvent,
    SnapshotCreatedEvent,
    TransitionDetectedEvent,
)
from sense_ai.model import (
    CapabilitySpec,
    CapabilityStatus,
    ContextMachine,
    ContextSnapshot,
    ContextTransition,
    TelemetryObservation,
)
from sense_ai.model.capability import capability
from sense_ai.model.result import CapabilityResult, ConstraintResult

# Re-export rules from the top-level for the most common imports (PRD §11.1)
from sense_ai.rules import (
    ALL,
    ANY,
    NONE_OF,
    NOT,
    ONLY_ONE,
    Constraint,
    ConstraintOutcome,
    Equals,
    Exists,
    Fresh,
    Gt,
    Gte,
    In,
    Lt,
    Lte,
    equals,
    exists,
    fresh,
    gt,
    gte,
    in_,
    lt,
    lte,
)

# Trust framework (FR-12, FR-13)
from sense_ai.trust import TrustDimension, TrustReport, compute_trust_report

__all__ = [
    # Core machine
    "ContextMachine",
    # Capability definition
    "CapabilitySpec",
    "capability",
    # Result types
    "CapabilityResult",
    "CapabilityStatus",
    "ConstraintResult",
    "ContextTransition",
    # Snapshot
    "ContextSnapshot",
    # Observation
    "TelemetryObservation",
    # Rules
    "Constraint",
    "ConstraintOutcome",
    "Equals",
    "Exists",
    "Fresh",
    "Gte",
    "Gt",
    "Lte",
    "Lt",
    "In",
    "ALL",
    "ANY",
    "NOT",
    "NONE_OF",
    "ONLY_ONE",
    # Convenience factories
    "equals",
    "exists",
    "fresh",
    "gte",
    "gt",
    "lte",
    "lt",
    "in_",
    # Trust framework
    "TrustDimension",
    "TrustReport",
    "compute_trust_report",
    # Events
    "CapabilityEvaluatedEvent",
    "EventBus",
    "EventHandler",
    "EventType",
    "RawEvent",
    "SnapshotCreatedEvent",
    "TransitionDetectedEvent",
    # Errors (FR-14)
    "SenseError",
    "SchemaValidationError",
    "InvalidRuleError",
    "UnknownCapabilityError",
    "MissingEvidenceError",
    "PeaqConfigurationError",
    "PeaqNetworkError",
    "UnsupportedPeaqFlowError",
    "SerializationError",
]

__version__ = "0.2.0"
