"""
Asynchronous event bus for capability evaluation lifecycle events.

All events are emitted from within the ``ContextMachine`` evaluation pipeline.
Subscribers can register for:

- ``capability_evaluated`` – after any single ``evaluate()`` call completes.
- ``snapshot_created``     – after ``snapshot()`` is called.
- ``transition_detected``  – when a ``ContextTransition`` is detected.

Usage::

    from sense_ai.events import EventBus, EventHandler

    bus = EventBus()

    @bus.on("capability_evaluated")
    def log_evaluation(event):
        print(f"{event.capability_name} → {event.result.status.name}")

    machine = ContextMachine(machine_id="unit-001", event_bus=bus)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Protocol, Sequence

from sense_ai.model.result import CapabilityResult, ContextTransition

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Event types
# ----------------------------------------------------------------------


class EventType(Enum):
    """Canonical event type identifiers."""

    CAPABILITY_EVALUATED = "capability_evaluated"
    SNAPSHOT_CREATED = "snapshot_created"
    TRANSITION_DETECTED = "transition_detected"


# ----------------------------------------------------------------------
# Event payloads
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class RawEvent:
    """
    Base class for all events emitted by the Sense engine.

    Attributes:
        event_type: The event type identifier.
        machine_id: Machine that generated the event.
        emitted_at: UTC timestamp of emission.
        payload: Serialisable event data.
    """

    event_type: EventType
    machine_id: str
    emitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "machine_id": self.machine_id,
            "emitted_at": self.emitted_at.isoformat(),
            "payload": self.payload,
        }


@dataclass(frozen=True)
class CapabilityEvaluatedEvent(RawEvent):
    """Emitted after a single capability is evaluated."""

    capability_name: str = ""
    result: CapabilityResult = field(default_factory=CapabilityResult)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", EventType.CAPABILITY_EVALUATED)
        object.__setattr__(
            self,
            "payload",
            {
                "capability_name": self.capability_name,
                "result": self.result.to_dict(),
            },
        )


@dataclass(frozen=True)
class SnapshotCreatedEvent(RawEvent):
    """Emitted after ``ContextMachine.snapshot()`` is called."""

    snapshot_dict: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", EventType.SNAPSHOT_CREATED)
        object.__setattr__(self, "payload", {"snapshot": self.snapshot_dict})


@dataclass(frozen=True)
class TransitionDetectedEvent(RawEvent):
    """Emitted when a ``ContextTransition`` is detected during evaluation."""

    transition: ContextTransition = field(default_factory=ContextTransition)

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_type", EventType.TRANSITION_DETECTED)
        object.__setattr__(
            self,
            "payload",
            {"transition": self.transition.to_dict()},
        )


# ----------------------------------------------------------------------
# EventHandler protocol
# ----------------------------------------------------------------------


class EventHandler(Protocol):
    """
    Protocol for event subscriber callables.

    A callable is a valid handler if it accepts a single ``RawEvent`` argument.

    Example::

        def my_handler(event: RawEvent) -> None:
            print(event.machine_id, event.event_type)

        bus.subscribe(my_handler)
    """

    def __call__(self, event: RawEvent) -> None: ...


# ----------------------------------------------------------------------
# EventBus
# ----------------------------------------------------------------------


class EventBus:
    """
    In-process event bus for publishing and subscribing to Sense lifecycle events.

    Thread-safety: the bus is thread-safe for subscription/unsubscription.
    Event delivery is synchronous on the calling thread (same-thread delivery).

    Filters are stored as sets so duplicate registrations are idempotent.

    Usage::

        bus = EventBus()

        @bus.on("capability_evaluated")
        def on_eval(event):
            print(event.capability_name)

        machine = ContextMachine(machine_id="u1", event_bus=bus)
        machine.evaluate("some_capability")
    """

    def __init__(self) -> None:
        # type → set of handlers
        self._handlers: dict[EventType, set[EventHandler]] = {
            EventType.CAPABILITY_EVALUATED: set(),
            EventType.SNAPSHOT_CREATED: set(),
            EventType.TRANSITION_DETECTED: set(),
        }
        self._all_handlers: set[EventHandler] = set()
        self._log = logging.getLogger(f"{__name__}.EventBus")

    # ------------------------------------------------------------------
    # Subscription API
    # ------------------------------------------------------------------

    def on(self, event_type: str | EventType) -> Callable[[EventHandler], EventHandler]:
        """
        Decorator to register a handler for ``event_type``.

        ``event_type`` may be a ``EventType`` enum value or its string name
        (e.g. ``"capability_evaluated"``).

        Example::

            @bus.on("transition_detected")
            def on_transition(event: TransitionDetectedEvent) -> None:
                print(event.transition.to_status)
        """

        def _register(fn: EventHandler) -> EventHandler:
            et = _normalise(event_type)
            self.subscribe(fn, event_type=et)
            return fn

        return _register

    def subscribe(
        self,
        handler: EventHandler,
        event_type: EventType | None = None,
    ) -> None:
        """
        Subscribe ``handler`` to events.

        Args:
            handler: A callable accepting a single ``RawEvent``.
            event_type: If provided, subscribe only to this type.
                If None, subscribe to *all* event types.
        """
        if event_type is None:
            self._all_handlers.add(handler)
        else:
            self._handlers[event_type].add(handler)

    def unsubscribe(
        self,
        handler: EventHandler,
        event_type: EventType | None = None,
    ) -> None:
        """Remove ``handler`` from the event bus."""
        if event_type is None:
            self._all_handlers.discard(handler)
        else:
            self._handlers[event_type].discard(handler)

    # ------------------------------------------------------------------
    # Publishing (called by ContextMachine)
    # ------------------------------------------------------------------

    def _publish(self, event: RawEvent) -> None:
        """
        Dispatch ``event`` to all matching subscribers.

        Called by ``ContextMachine`` internals.  Errors in handlers are logged
        but never propagated to the caller.
        """
        # All-type handlers
        for handler in list(self._all_handlers):
            _deliver(handler, event, self._log)

        # Type-specific handlers
        for handler in list(self._handlers.get(event.event_type, ())):
            _deliver(handler, event, self._log)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def subscriber_count(self) -> int:
        """Total number of registered handlers (including all-type)."""
        all_types = sum(len(s) for s in self._handlers.values())
        return all_types + len(self._all_handlers)

    def subscribed_handlers(
        self, event_type: EventType | None = None
    ) -> Sequence[EventHandler]:
        """Return a list of handlers registered for ``event_type`` (or all)."""
        if event_type is None:
            return list(self._all_handlers)
        return list(self._handlers.get(event_type, ()))


# ----------------------------------------------------------------------
# Utilities
# ----------------------------------------------------------------------


def _normalise(event_type: str | EventType) -> EventType:
    if isinstance(event_type, EventType):
        return event_type
    try:
        return EventType(event_type)
    except ValueError as exc:
        raise ValueError(
            f"Unknown event type {event_type!r}. "
            f"Valid values: {[e.value for e in EventType]}"
        ) from exc


def _deliver(
    handler: EventHandler,
    event: RawEvent,
    log: logging.Logger,
) -> None:
    try:
        handler(event)
    except Exception:
        log.exception(
            "Event handler %s raised for event %s on machine %s",
            getattr(handler, "__name__", repr(handler)),
            event.event_type.value,
            event.machine_id,
        )
