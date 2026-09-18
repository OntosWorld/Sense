"""Event type definitions — FR-7 async event bus (capability_evaluated / snapshot_created / transition_detected)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sense_ai.model.result import ContextTransition

# ------------------------------------------------------------------
# Public re-exports (also used by the main package __init__)
# ------------------------------------------------------------------
__all__ = [
    # Raw / base
    "Event",
    "EventSchema",
    "EventSeverity",
    "EventSeverityT",
    "RawEvent",
    # FR-7 EventType enum
    "EventType",
    # FR-7 typed event payloads
    "CapabilityEvaluatedEvent",
    "SnapshotCreatedEvent",
    "TransitionDetectedEvent",
    # Handler protocol
    "EventHandler",
    # EventBus
    "EventBus",
]

# ------------------------------------------------------------------
# Raw inbound event (unvalidated)
# ------------------------------------------------------------------
RawEvent = dict[str, Any]


# ------------------------------------------------------------------
# Existing types (preserved from the original events package)
# ------------------------------------------------------------------


class EventSeverity(str, Enum):
    """Severity level of an event."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


EventSeverityT = EventSeverity


@dataclass(frozen=True)
class EventSchema:
    """Reference to the JSON Schema that defines this event's structure."""

    uri: str = ""


@dataclass(frozen=True)
class Event:
    """
    A typed, immutable evaluation event.

    Attributes
    ----------
    schema : EventSchema
        Schema reference for the event payload.
    timestamp : datetime
        When the event occurred (UTC).
    agent_id : str
        Identifier of the agent that emitted or is associated with this event.
    event_type : str
        Semantic type name (e.g., "capability.invoked", "context.changed").
    payload : dict[str, Any]
        Arbitrary event data.
    severity : EventSeverity
        Event severity level.
    context_ref : str, optional
        Reference to the context snapshot this event belongs to.
    trace_id : str, optional
        Distributed trace identifier.
    """

    schema: EventSchema = field(default_factory=EventSchema)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    agent_id: str = ""
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    severity: EventSeverity = EventSeverity.INFO
    context_ref: str | None = None
    trace_id: str | None = None


# ------------------------------------------------------------------
# FR-7 EventType enum
# ------------------------------------------------------------------


class EventType(Enum):
    """
    Enumerated FR-7 lifecycle event types emitted by :class:`ContextMachine`.

    - ``CAPABILITY_EVALUATED`` — after every evaluate() / evaluate_all() call
    - ``SNAPSHOT_CREATED`` — after every snapshot() call
    - ``TRANSITION_DETECTED`` — when a registered capability's status changes
    """

    CAPABILITY_EVALUATED = "capability_evaluated"
    SNAPSHOT_CREATED = "snapshot_created"
    TRANSITION_DETECTED = "transition_detected"


# ------------------------------------------------------------------
# FR-7 typed event payloads
# ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CapabilityEvaluatedEvent:
    """
    Emitted by :meth:`ContextMachine.evaluate` and :meth:`ContextMachine.evaluate_all`.

    Attributes
    ----------
    machine_id : str
        The machine's reference string.
    capability_name : str | None
        Name of the specific capability evaluated, or None for evaluate_all.
    result : dict
        Serialised :class:`CapabilityResult`.
    """

    machine_id: str
    capability_name: str | None
    result: dict[str, Any]

    def to_raw(self) -> dict[str, Any]:
        return {
            "type": EventType.CAPABILITY_EVALUATED.value,
            "machine_id": self.machine_id,
            "capability_name": self.capability_name,
            "result": self.result,
        }


@dataclass(frozen=True, slots=True)
class SnapshotCreatedEvent:
    """
    Emitted by :meth:`ContextMachine.snapshot`.

    Attributes
    ----------
    machine_id : str
        The machine's reference string.
    snapshot_dict : dict
        Serialised :class:`ContextSnapshot`.
    """

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
    """
    Emitted by :meth:`ContextMachine.evaluate` when a registered capability's
    status transitions between evaluation cycles.

    Parameters
    ----------
    machine_id : str
        The machine's reference string.
    transition : ContextTransition
        The transition that was detected.

    Attributes (derived from ``transition``)
    ---------------------------------------
    capability_name : str
        Name of the capability that transitioned.
    previous_status : str
        Status before the transition (value of :attr:`CapabilityStatus`).
    current_status : str
        Status after the transition (value of :attr:`CapabilityStatus`).
    """

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
            "capability_name": self.capability_name,
            "previous_status": self.previous_status,
            "current_status": self.current_status,
        }


# ------------------------------------------------------------------
# Handler protocol
# ------------------------------------------------------------------


@runtime_checkable
class EventHandler(Protocol):
    """
    Concrete event handler signature.

    Accepts the event payload dataclass (one of
    :class:`CapabilityEvaluatedEvent`, :class:`SnapshotCreatedEvent`,
    :class:`TransitionDetectedEvent`) and optionally returns a value.
    Raising an exception from a handler will be caught and logged by
    :class:`EventBus` — it will not propagate.
    """

    def __call__(
        self,
        event: CapabilityEvaluatedEvent
        | SnapshotCreatedEvent
        | TransitionDetectedEvent,
    ) -> Any: ...


# ------------------------------------------------------------------
# EventBus
# ------------------------------------------------------------------


class EventBus:
    """
    Synchronous in-process event bus for FR-7 lifecycle events.

    Supports three event types: ``capability_evaluated``,
    ``snapshot_created``, and ``transition_detected``.

    Delivery is **synchronous on the calling thread**. Handlers are invoked
    in registration order; any exception raised by a handler is caught,
    logged via the standard ``logging`` module, and swallowed so that
    remaining handlers continue to run.

    Usage::

        bus = EventBus()
        bus.subscribe(EventType.CAPABILITY_EVALUATED, my_handler)
        machine = ContextMachine(event_bus=bus)
        machine.evaluate(...)   # my_handler is called synchronously

    String literals (``"capability_evaluated"``, ``"snapshot_created"``,
    ``"transition_detected"``) are accepted anywhere an ``EventType`` is
    accepted.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandler]] = {
            et: [] for et in EventType
        }
        self._all_handlers: list[EventHandler] = []  # catch-all handlers
        self._logger = logging.getLogger("Sense.events.EventBus")

    # ------------------------------------------------------------------
    # Subscription
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type_or_handler: EventType | EventHandler,
        handler: EventHandler | None = None,
    ) -> None:
        """Register ``handler`` to receive events.

        Two-argument form: ``subscribe(EventType.XXX, handler)`` — receive only
        that event type.
        One-argument form: ``subscribe(handler)`` — receive all event types.
        """
        if handler is None:
            # One-arg form: subscribe to all types
            self._all_handlers.append(event_type_or_handler)  # type: ignore[arg-type]
        else:
            # 2-arg form: event_type_or_handler is EventType
            self._handlers[event_type_or_handler].append(handler)  # type: ignore[index]

    def unsubscribe(
        self,
        event_type_or_handler: EventType | EventHandler,
        handler: EventHandler | None = None,
    ) -> None:
        """Remove ``handler``.

        Two-argument form: ``unsubscribe(EventType.XXX, handler)``.
        One-argument form: ``unsubscribe(handler)`` — remove from all types.
        """
        if handler is None:
            # One-arg form: remove from all types
            try:
                self._all_handlers.remove(event_type_or_handler)  # type: ignore[arg-type]
            except ValueError:
                pass
        else:
            # 2-arg form
            try:
                self._handlers[event_type_or_handler].remove(handler)  # type: ignore[index]
            except (KeyError, ValueError):
                pass

    def on(
        self,
        event_type: EventType
        | Literal["capability_evaluated", "snapshot_created", "transition_detected"],
    ) -> Callable[[EventHandler], EventHandler]:
        """
        Decorator equivalent of :meth:`subscribe`.

        Accepts either an ``EventType`` enum value or a string literal
        (``"capability_evaluated"``, ``"snapshot_created"``,
        ``"transition_detected"``).

        Example::

            bus = EventBus()

            @bus.on("capability_evaluated")
            def log_evaluation(event: CapabilityEvaluatedEvent) -> None:
                print(event.machine_id, event.capability_name)
        """
        # Normalise string literal to EventType
        if isinstance(event_type, str):
            event_type = EventType(event_type)

        def decorator(handler: EventHandler) -> EventHandler:
            self.subscribe(event_type, handler)
            return handler

        return decorator

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    def _event_type_for(self, payload: object) -> EventType:
        """Derive the EventType for a given payload class."""
        if isinstance(payload, CapabilityEvaluatedEvent):
            return EventType.CAPABILITY_EVALUATED
        if isinstance(payload, SnapshotCreatedEvent):
            return EventType.SNAPSHOT_CREATED
        if isinstance(payload, TransitionDetectedEvent):
            return EventType.TRANSITION_DETECTED
        raise ValueError(f"Unknown event payload type: {type(payload)!r}")

    def _publish(
        self,
        payload: CapabilityEvaluatedEvent
        | SnapshotCreatedEvent
        | TransitionDetectedEvent,
    ) -> None:
        """
        Synchronously dispatch ``payload`` to all registered handlers.

        Errors in individual handlers are caught and logged; they do not
        prevent remaining handlers from running.
        """
        event_type = self._event_type_for(payload)

        for handler in self._handlers[event_type]:
            try:
                handler(payload)
            except Exception:  # noqa: BLE001  — swallow per spec
                self._logger.exception("EventBus handler %s raised", handler)

        for handler in self._all_handlers:
            try:
                handler(payload)
            except Exception:  # noqa: BLE001
                self._logger.exception("EventBus all-handler %s raised", handler)

    def publish(
        self,
        payload: CapabilityEvaluatedEvent
        | SnapshotCreatedEvent
        | TransitionDetectedEvent,
    ) -> None:
        """Public alias for :meth:`_publish`."""
        self._publish(payload)
