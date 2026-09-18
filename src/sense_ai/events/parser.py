"""Event parser: converts raw event payloads into typed Event objects."""

from __future__ import annotations

from .types import Event, EventSchema, EventSeverity, RawEvent


class EventParser:
    """
    Parses raw event dictionaries into strongly-typed :class:`Event` objects.

    Raises
    ------
    EventParseError
        When the raw payload is structurally invalid.
    """

    def parse(self, raw: RawEvent) -> Event:
        """Parse a single raw event dict into an Event."""
        schema_ref = raw.get("schema")
        schema = EventSchema(uri=schema_ref) if schema_ref else EventSchema()

        severity_str = raw.get("severity", "info")
        severity = EventSeverity(severity_str)

        return Event(
            schema=schema,
            timestamp=raw["timestamp"],
            agent_id=raw["agent_id"],
            event_type=raw["event_type"],
            payload=raw.get("payload", {}),
            severity=severity,
            context_ref=raw.get("context_ref"),
            trace_id=raw.get("trace_id"),
        )

    def parse_many(self, raw_events: list[RawEvent]) -> list[Event]:
        """Parse a list of raw events."""
        return [self.parse(e) for e in raw_events]


class EventParseError(ValueError):
    """Raised when a raw event cannot be parsed into an Event."""


# Convenience singleton
parser = EventParser()
