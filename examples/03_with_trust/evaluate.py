"""Evidence-quality example for the current Sense machine context."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sense_ai import (
    ContextMachine,
    TelemetryObservation,
    capability,
    compute_evidence_quality,
    equals,
    fresh,
    gte,
)


def build_machine() -> ContextMachine:
    machine = ContextMachine(machine_ref="inspection-robot-01")
    machine.define_capability(
        capability(
            "inspection.ready",
            requires=[
                equals("safety.estop", False),
                gte("battery.level_pct", 20),
                fresh("localization.pose", max_age_ms=2000),
            ],
        )
    )
    return machine


def ingest(machine: ContextMachine, *, stale_pose: bool = False) -> None:
    now = datetime.now(timezone.utc)
    pose_time = now - timedelta(seconds=30) if stale_pose else now

    observations = [
        TelemetryObservation(
            path="safety.estop",
            value=False,
            observed_at=now,
            source="plc",
            ttl_ms=1000,
        ),
        TelemetryObservation(
            path="battery.level_pct",
            value=74,
            observed_at=now,
            source="bms",
            ttl_ms=2000,
        ),
        TelemetryObservation(
            path="localization.pose",
            value={"x": 1.0, "y": 0.5},
            observed_at=pose_time,
            source="localization",
            ttl_ms=2000,
        ),
    ]

    for observation in observations:
        machine.observe(observation)


def show(name: str, machine: ContextMachine) -> None:
    snapshot = machine.snapshot()
    report = compute_evidence_quality(
        schema_version=snapshot.schema_version,
        machine_id=snapshot.machine_ref or "",
        observations=list(snapshot.observations.values()),
        required_observation_paths=frozenset(
            {
                "safety.estop",
                "battery.level_pct",
                "localization.pose",
            }
        ),
    )

    print(f"\n{name}")
    print("capability:", snapshot.capabilities["inspection.ready"].status.value)
    print("evidence quality:", report.quality_band, f"{report.overall_score:.3f}")
    for dimension in report.dimensions:
        print(f"  {dimension.name}: {dimension.score:.3f}")


def main() -> None:
    healthy = build_machine()
    ingest(healthy)
    show("Healthy evidence", healthy)

    stale = build_machine()
    ingest(stale, stale_pose=True)
    show("Stale localization evidence", stale)


if __name__ == "__main__":
    main()
