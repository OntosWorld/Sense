"""Events subsystem: typed event ingestion and FR-7 event bus."""

from __future__ import annotations

from .types import (
    # FR-7 payloads
    CapabilityEvaluatedEvent,
    # Raw / base
    Event,
    # EventBus (also in types.py for convenience)
    EventBus,
    # Handler
    EventHandler,
    EventSchema,
    EventSeverity,
    EventSeverityT,
    # FR-7 enum
    EventType,
    RawEvent,
    SnapshotCreatedEvent,
    TransitionDetectedEvent,
)

__all__ = [
    # Raw / base
    "Event",
    "EventSchema",
    "EventSeverity",
    "EventSeverityT",
    "RawEvent",
    # FR-7 enum
    "EventType",
    # FR-7 payloads
    "CapabilityEvaluatedEvent",
    "SnapshotCreatedEvent",
    "TransitionDetectedEvent",
    # Handler
    "EventHandler",
    # EventBus
    "EventBus",
]
