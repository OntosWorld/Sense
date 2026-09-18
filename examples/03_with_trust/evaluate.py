"""
Trust evaluation: run a trust report alongside capability evaluation
to get a trustworthiness verdict for the current machine situation.

Demonstrates:
  - compute_trust_report() with a ContextSnapshot
  - TrustDimensions: HONESTY, RECENCY, CONSISTENCY, COVERAGE, RESILIENCE
  - TrustReport fields: verdict, trust_score, dimension_scores, reasoning

Run from the repo root::

    PYTHONPATH=src python examples/03_with_trust/evaluate.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from sense_ai import (
    ContextMachine,
    TelemetryObservation,
    capability,
    equals,
    gte,
    fresh,
)
from sense_ai.trust import compute_trust_report


def _build_machine() -> ContextMachine:
    """Create and populate a machine with varied telemetry."""
    machine = ContextMachine(machine_ref="inspection-robot-01")

    machine.define_capability(
        capability(
            "inspection.ready",
            version="1.0",
            requires=[
                equals("safety.estop", False),
                gte("battery.level_pct", 20),
                fresh("localization.pose", max_age_ms=2000),
            ],
        )
    )

    return machine


def _ingest_healthy(machine: ContextMachine) -> None:
    """All sensors reporting correctly, recent observations."""
    now = datetime.now(timezone.utc)
    for obs in [
        TelemetryObservation(path="safety.estop",         value=False,      observed_at=now, source="plc",   ttl_ms=1000),
        TelemetryObservation(path="battery.level_pct",    value=74,        observed_at=now, source="bms",   ttl_ms=2000),
        TelemetryObservation(path="localization.pose",    value={"x": 1.0, "y": 0.5}, observed_at=now, source="lidar", ttl_ms=500),
        TelemetryObservation(path="sensor.vision.active", value=True,      observed_at=now, source="vision", ttl_ms=5000),
        TelemetryObservation(path="sensor.lidar.active",  value=True,      observed_at=now, source="lidar", ttl_ms=5000),
        TelemetryObservation(path="motor.winding_temp_c", value=68.0,      observed_at=now, source="mcu",  ttl_ms=2000),
    ]:
        machine.observe(obs)


def _ingest_stale(machine: ContextMachine) -> None:
    """Pose is too old — freshness constraint will fail."""
    now = datetime.now(timezone.utc)
    for obs in [
        TelemetryObservation(path="safety.estop",         value=False,     observed_at=now, source="plc",  ttl_ms=1000),
        TelemetryObservation(path="battery.level_pct",    value=74,       observed_at=now, source="bms",  ttl_ms=2000),
        # Deliberately old pose (30 seconds ago — exceeds 2-second freshness)
        TelemetryObservation(
            path="localization.pose",
            value={"x": 1.0, "y": 0.5},
            observed_at=datetime.fromtimestamp(0, tz=timezone.utc),  # epoch — very stale
            source="lidar",
            ttl_ms=2000,
        ),
        TelemetryObservation(path="sensor.vision.active", value=True,    observed_at=now, source="vision", ttl_ms=5000),
        TelemetryObservation(path="sensor.lidar.active",  value=True,    observed_at=now, source="lidar", ttl_ms=5000),
        TelemetryObservation(path="motor.winding_temp_c", value=68.0,     observed_at=now, source="mcu",  ttl_ms=2000),
    ]:
        machine.observe(obs)


def _ingest_sparse(machine: ContextMachine) -> None:
    """Only a few sensors reporting — low COVERAGE score."""
    now = datetime.now(timezone.utc)
    for obs in [
        TelemetryObservation(path="safety.estop",      value=False, observed_at=now, source="plc",  ttl_ms=1000),
        TelemetryObservation(path="battery.level_pct",  value=74,   observed_at=now, source="bms",  ttl_ms=2000),
        TelemetryObservation(path="localization.pose",  value={"x": 1.0, "y": 0.5}, observed_at=now, source="lidar", ttl_ms=500),
        # No motor, no vision, no lidar — sparse coverage
    ]:
        machine.observe(obs)


def main() -> None:
    scenarios = [
        ("Healthy robot", _ingest_healthy),
        ("Stale pose — freshness constraint fails", _ingest_stale),
        ("Sparse sensors — low coverage", _ingest_sparse),
    ]

    for name, ingest_fn in scenarios:
        machine = _build_machine()
        ingest_fn(machine)

        snapshot = machine.snapshot()
        report = compute_trust_report(
            schema_version=snapshot.schema_version,
            machine_id=snapshot.machine_ref,
            observations=list(snapshot.observations.values()),
        )

        band_icon = {
            "excellent": "✅",
            "good": "👍",
            "fair": "⚠️ ",
            "poor": "⚠️ ",
            "critical": "❌",
        }.get(report.quality_band, "?")

        print(f"\n{'─' * 60}")
        print(f"  {name}")
        print(f"{'─' * 60}")
        print(f"  Quality  : {band_icon} {report.quality_band}")
        print(f"  Score    : {report.overall_score:.3f}  (0.0–1.0)")
        print(f"  Obs count: {report.observation_count}")
        print(f"  Computed : {report.timestamp.isoformat()}")
        print(f"  Dimensions:")

        for dim in report.dimensions:
            bar = "█" * int(dim.score * 10) + "░" * (10 - int(dim.score * 10))
            print(f"    {dim.name:<20} [{bar}]  {dim.score:.3f}  (weight={dim.weight:.1f})")


if __name__ == "__main__":
    main()
