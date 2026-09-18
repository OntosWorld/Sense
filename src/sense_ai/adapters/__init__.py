"""Transport-neutral adapter contracts for feeding telemetry into Sense."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any, Protocol

from sense_ai.telemetry import NormalizationResult, TelemetryNormalizer


class AdapterError(Exception):
    """Base exception for transport adapter failures."""


class ObservationSink(Protocol):
    """Minimal machine surface required by telemetry adapters."""

    def observe(self, *args: Any, **kwargs: Any) -> Any: ...


class TelemetryAdapter(ABC):
    """Lifecycle contract implemented by external telemetry transports."""

    @abstractmethod
    def start(self) -> None:
        """Start receiving telemetry."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop receiving telemetry and release resources."""
        ...


class MappedTelemetryAdapter:
    """Reusable base for adapters that receive mapping-like payloads."""

    def __init__(
        self,
        machine: ObservationSink,
        normalizer: TelemetryNormalizer,
    ) -> None:
        self.machine = machine
        self.normalizer = normalizer

    def ingest_payload(
        self,
        payload: Mapping[str, Any] | Any,
        **kwargs: Any,
    ) -> NormalizationResult:
        result = self.normalizer.normalize(payload, **kwargs)
        for observation in result.observations:
            self.machine.observe(observation)
        return result


__all__ = [
    "AdapterError",
    "MappedTelemetryAdapter",
    "ObservationSink",
    "TelemetryAdapter",
]
