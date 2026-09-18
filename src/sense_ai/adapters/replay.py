"""Deterministic offline telemetry replay adapter."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sense_ai.adapters import MappedTelemetryAdapter
from sense_ai.telemetry import NormalizationResult, TelemetryNormalizer


@dataclass(frozen=True, slots=True)
class ReplayFrame:
    """One raw payload frame for simulator/offline replay."""

    payload: Mapping[str, Any] | Any
    observed_at: datetime | None = None
    received_at: datetime | None = None
    source: str = "replay"


class ReplayAdapter(MappedTelemetryAdapter):
    """Feed recorded/simulated raw machine frames through the normalizer."""

    def __init__(
        self,
        machine: Any,
        normalizer: TelemetryNormalizer,
        frames: Iterable[ReplayFrame],
        *,
        evaluate_after_frame: bool = False,
    ) -> None:
        super().__init__(machine, normalizer)
        self._frames = frames
        self._evaluate_after_frame = evaluate_after_frame
        self._running = False

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> list[NormalizationResult]:
        self.start()
        results: list[NormalizationResult] = []
        try:
            for frame in self._frames:
                if not self._running:
                    break
                results.append(
                    self.ingest_payload(
                        frame.payload,
                        observed_at=frame.observed_at,
                        received_at=frame.received_at,
                        source=frame.source,
                    )
                )
                if self._evaluate_after_frame:
                    self.machine.evaluate_all()
        finally:
            self.stop()
        return results
