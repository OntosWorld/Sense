"""Trace model: telemetry captured during an evaluation run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Trace:
    """
    A structured log of telemetry captured during an evaluation.

    Attributes
    ----------
    trace_id : str
        Globally unique identifier for this trace.
    span_id : str, optional
        Identifier for this span within the trace.
    events : list[dict[str, Any]]
        Key events recorded in order.
    attributes : dict[str, Any]
        Open-key attributes attached to this span.
    """

    trace_id: str
    span_id: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def add_event(self, name: str, data: dict[str, Any] | None = None) -> None:
        """Append a named event to this trace."""
        self.events.append({"name": name, "data": data or {}})
