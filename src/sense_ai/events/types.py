"""Typed lifecycle events and synchronous in-process event bus."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sense_ai.model.result import CapabilityResult, ContextTransition

RawEvent = dict[str, Any]


class EventSeverity(str, Enum):
    """Severity level for generic parsed events."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


EventSeverityT = EventSeverity


@dataclass(frozen=True, slots=True)
class EventSchema:
    """Reference to a schema describing a generic inbound event."""

    uri: str = ""


@dataclass(frozen=True, slots=True)
class Event:
    """Generic typed event used by EventParser."""

    schema: EventSchema = field(default_factory=EventSchema)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    severity: EventSeverity = EventSeverity.INFO
    context_ref: str | None = None
    trace_id: str | None = None


class EventType(str, Enum):
    """Sense runtime lifecycle event types."""

    CAPABILITY_EVALUATED = "capability_evaluated"
    SNAPSHOT_CREATED = "snapshot_created"
    TRANSITION_DETECTED = "transition_detected"


@dataclass(frozen=True, slots=True)
class CapabilityEvaluatedEvent:
    """Emitted after one capability evaluation."""

    machine_id: str
    capability_name: str | None
    result: CapabilityResult

    def to_raw(self) -> dict[str, Any]:
        return {
            "type": EventType.CAPABILITY_EVALUATED.value,
            "machine_id": self.machine_id,
            "capability_name": self.capability_name,
            "result": self.result.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class SnapshotCreatedEvent:
    """Emitted after a context snapshot is created."""

    machine_id: str
    snapshot_dict: dict[str, Any]

    def to_raw(self) -> dict[str, Any]:
        return {
            "type": EventType.SNAPSHOT_CREATED.value,
            "machine_id": self.machine_id,
            "snapshot": self.snapshot_dict,
        }


@dataclass(frozen=True, slots=True)
class TransitionDetectedEvent:
    """Emitted when a capability changes state."""

    machine_id: str
    transition: ContextTransition

    @property
    def capability_name(self) -> str:
        return self.transition.capability

    @property
    def previous_status(self) -> str:
        return self.transition.previous.value if self.transition.previous else "NONE"

    @property
    def current_status(self) -> str:
        return self.transition.current.value

    def to_raw(self) -> dict[str, Any]:
        return {
            "type": EventType.TRANSITION_DETECTED.value,
            "machine_id": self.machine_id,
            "transition": self.transition.to_dict(),
        }


LifecycleEvent = CapabilityEvaluatedEvent | SnapshotCreatedEvent | TransitionDetectedEvent


@runtime_checkable
class EventHandler(Protocol):
    """Callable lifecycle event subscriber."""

    def __call__(self, event: LifecycleEvent) -> Any: ...


class EventBus:
    """Synchronous, in-process event bus for Sense lifecycle events."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {
            event_type: [] for event_type in EventType
        }
        self._all_handlers: list[EventHandler] = []
        self._logger = logging.getLogger("sense_ai.events.EventBus")

    def subscribe(
        self,
        event_type_or_handler: EventType | str | EventHandler,
        handler: EventHandler | None = None,
    ) -> None:
        """Subscribe to one event type or to all events."""
        if handler is None:
            if not callable(event_type_or_handler):
                raise TypeError("single-argument subscribe() requires a handler")
            self._all_handlers.append(event_type_or_handler)
            return

        event_type = _normalise_event_type(event_type_or_handler)
        self._handlers[event_type].append(handler)

    def unsubscribe(
        self,
        event_type_or_handler: EventType | str | EventHandler,
        handler: EventHandler | None = None,
    ) -> None:
        """Remove a lifecycle event subscription."""
        if handler is None:
            if callable(event_type_or_handler):
                try:
                    self._all_handlers.remove(event_type_or_handler)
                except ValueError:
                    pass
            return

        event_type = _normalise_event_type(event_type_or_handler)
        try:
            self._handlers[event_type].remove(handler)
        except ValueError:
            pass

    def on(
        self,
        event_type: EventType
        | Literal[
            "capability_evaluated",
            "snapshot_created",
            "transition_detected",
        ],
    ) -> Callable[[EventHandler], EventHandler]:
        """Decorator form of subscribe()."""
        normalised = _normalise_event_type(event_type)

        def decorator(handler: EventHandler) -> EventHandler:
            self._handlers[normalised].append(handler)
            return handler

        return decorator

    def publish(self, event: LifecycleEvent) -> None:
        """Publish an event to matching subscribers."""
        self._publish(event)

    def _publish(self, event: LifecycleEvent) -> None:
        event_type = _event_type_for(event)
        for handler in [*self._handlers[event_type], *self._all_handlers]:
            try:
                handler(event)
            except Exception:
                self._logger.exception(
                    "Event handler %r failed for %s",
                    handler,
                    event_type.value,
                )

    @property
    def subscriber_count(self) -> int:
        return len(self._all_handlers) + sum(
            len(handlers) for handlers in self._handlers.values()
        )


def _normalise_event_type(value: EventType | str | EventHandler) -> EventType:
    if isinstance(value, EventType):
        return value
    if isinstance(value, str):
        return EventType(value)
    raise TypeError("event type must be an EventType or string")


def _event_type_for(event: LifecycleEvent) -> EventType:
    if isinstance(event, CapabilityEvaluatedEvent):
        return EventType.CAPABILITY_EVALUATED
    if isinstance(event, SnapshotCreatedEvent):
        return EventType.SNAPSHOT_CREATED
    if isinstance(event, TransitionDetectedEvent):
        return EventType.TRANSITION_DETECTED
    raise TypeError(f"unsupported lifecycle event: {type(event)!r}")


__all__ = [
    "CapabilityEvaluatedEvent",
    "Event",
    "EventBus",
    "EventHandler",
    "EventSchema",
    "EventSeverity",
    "EventSeverityT",
    "EventType",
    "LifecycleEvent",
    "RawEvent",
    "SnapshotCreatedEvent",
    "TransitionDetectedEvent",
]
