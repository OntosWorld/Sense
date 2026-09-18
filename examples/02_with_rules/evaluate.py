"""
Evaluation with rules: use declarative constraint expressions to define
capability requirements, then run a full evaluation cycle.

Demonstrates:
  - Rule primitives: equals, gte, lt, exists, fresh, in_
  - Logical composition: ALL, ANY, NOT, NONE_OF, ONLY_ONE
  - Per-constraint naming and severity (blocking / warning)
  - ConstraintOutcome inspection after evaluation

Run from the repo root::

    PYTHONPATH=src python examples/02_with_rules/evaluate.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from sense_ai import (
    ContextMachine,
    TelemetryObservation,
    capability,
    equals,
    gte,
    lt,
    exists,
    fresh,
    in_,
    ALL,
    ANY,
    NOT,
    NONE_OF,
    ONLY_ONE,
)


# ── Machine factory (module-level to allow fresh instances per scenario) ──────

def _configure_machine(machine: ContextMachine) -> None:
    """Define all four capabilities on a fresh machine instance."""
    # ── 1. Declares constraints with the @capability decorator ─────────────────

    machine.define_capability(
        capability(
            "inspection.ready",
            version="1.0",
            requires=[
                equals("safety.estop", False),
                gte("battery.level_pct", 20),
                equals("gripper.fault_code", 0),
                fresh("localization.pose", max_age_ms=2000),
                in_("mode.current", ["autonomous", "semi-auto", "idle"]),
            ],
            degrade_when=[
                lt("battery.level_pct", 30),
                gte("motor.winding_temp_c", 75),
            ],
        )
    )

    machine.define_capability(
        capability(
            "perception.available",
            version="1.0",
            requires=[
                ANY(
                    equals("sensor.vision.active", True),
                    equals("sensor.lidar.active", True),
                    equals("sensor.radar.active", True),
                ),
                ONLY_ONE(
                    equals("sensor.vision.primary", True),
                    equals("sensor.lidar.primary", True),
                ),
            ],
        )
    )

    machine.define_capability(
        capability(
            "operation.enabled",
            version="1.0",
            requires=[
                NOT(equals("mode.current", "maintenance")),
                NOT(equals("mode.current", "calibration")),
                ANY(
                    equals("network.connected", True),
                    equals("mode.offline_capable", True),
                ),
            ],
        )
    )

    machine.define_capability(
        capability(
            "diagnostics.clear",
            version="1.0",
            requires=[
                NONE_OF(
                    equals("fault.code", 1),
                    equals("fault.code", 2),
                    equals("fault.code", 3),
                    equals("fault.code", 99),
                ),
                exists("fault.last_reset"),
            ],
        )
    )


def _ingest_healthy(machine: ContextMachine) -> None:
    """Simulate a fully operational robot."""
    now = datetime.now(timezone.utc)
    for obs in [
        TelemetryObservation(path="safety.estop",         value=False,    observed_at=now, source="plc",    ttl_ms=1000),
        TelemetryObservation(path="battery.level_pct",    value=74,       observed_at=now, source="bms",    ttl_ms=2000),
        TelemetryObservation(path="gripper.fault_code",  value=0,        observed_at=now, source="gripper", ttl_ms=5000),
        TelemetryObservation(path="localization.pose",    value={"x": 1.2, "y": 0.8}, observed_at=now, source="lidar", ttl_ms=500),
        TelemetryObservation(path="mode.current",         value="autonomous", observed_at=now, source="plc", ttl_ms=1000),
        TelemetryObservation(path="sensor.vision.active", value=True,     observed_at=now, source="vision",  ttl_ms=5000),
        TelemetryObservation(path="sensor.vision.primary", value=True,    observed_at=now, source="vision",  ttl_ms=5000),
        TelemetryObservation(path="sensor.lidar.active", value=True,      observed_at=now, source="lidar",  ttl_ms=5000),
        TelemetryObservation(path="sensor.lidar.primary", value=False,    observed_at=now, source="lidar",  ttl_ms=5000),
        TelemetryObservation(path="sensor.radar.active", value=False,     observed_at=now, source="radar",  ttl_ms=5000),
        TelemetryObservation(path="motor.winding_temp_c", value=68.0,     observed_at=now, source="mcu",    ttl_ms=2000),
        TelemetryObservation(path="fault.code",           value=0,        observed_at=now, source="mcu",    ttl_ms=1000),
        TelemetryObservation(path="fault.last_reset",     value="2025-01-10", observed_at=now, source="mcu", ttl_ms=60000),
        TelemetryObservation(path="network.connected",    value=True,     observed_at=now, source="nm",    ttl_ms=5000),
        TelemetryObservation(path="mode.offline_capable", value=False,    observed_at=now, source="plc",    ttl_ms=1000),
    ]:
        machine.observe(obs)


def _ingest_degraded(machine: ContextMachine) -> None:
    """Simulate a robot with battery below the degrade threshold."""
    _ingest_healthy(machine)
    now = datetime.now(timezone.utc)
    machine.observe(TelemetryObservation(
        path="battery.level_pct",
        value=24,
        observed_at=now,
        source="bms",
        ttl_ms=2000,
    ))


def _ingest_unavailable(machine: ContextMachine) -> None:
    """Simulate a robot with estop engaged — capability should be UNAVAILABLE."""
    now = datetime.now(timezone.utc)
    machine.observe(TelemetryObservation(path="battery.level_pct",  value=74,  observed_at=now, source="bms",    ttl_ms=2000))
    machine.observe(TelemetryObservation(path="safety.estop",       value=True, observed_at=now, source="plc",    ttl_ms=1000))


def _evaluate(name: str, machine: ContextMachine) -> None:
    """Run all four capability evaluations and print results."""
    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")
    for cap_name in ["inspection.ready", "perception.available",
                      "operation.enabled", "diagnostics.clear"]:
        result = machine.evaluate(cap_name)
        icon = {"AVAILABLE": "✅", "DEGRADED": "⚠️ ", "UNAVAILABLE": "❌", "UNKNOWN": "❓"}[result.status.name]
        print(f"  {icon}  {cap_name}: {result.status.name}")
        if result.warnings:
            for w in result.warnings:
                print(f"      ⚡  {w}")
        if result.blocking:
            for b in result.blocking:
                print(f"      ✖   {b.path}  [{b.constraint_name or b.code}]  actual={b.observed}")


def main() -> None:
    scenarios = [
        ("Healthy robot",              _ingest_healthy),
        ("Degraded robot (low battery)", _ingest_degraded),
        ("Unavailable robot (estop)",   _ingest_unavailable),
    ]

    for name, ingest_fn in scenarios:
        machine = ContextMachine(machine_ref="inspection-robot-01")
        _configure_machine(machine)
        ingest_fn(machine)
        _evaluate(name, machine)

    # ── 7. Inspect constraint outcomes ────────────────────────────────────────

    print(f"\n{'─' * 60}")
    print("  Constraint outcome inspection")
    print(f"{'─' * 60}")

    machine = ContextMachine(machine_ref="inspection-robot-01")
    _configure_machine(machine)
    _ingest_healthy(machine)
    result = machine.evaluate("inspection.ready")

    for outcome in result.blocking + result.warnings:
        stale_tag = " [STALE]" if outcome.is_stale else ""
        absent_tag = " [ABSENT]" if outcome.is_absent else ""
        print(
            f"  ❌  [{outcome.code}]"
            f"  path={outcome.path!r}"
            f"  expected={outcome.expected}"
            f"  observed={outcome.observed!r}"
            f"  age_ms={outcome.observed_age_ms}{stale_tag}{absent_tag}"
        )


if __name__ == "__main__":
    main()
