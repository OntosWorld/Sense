"""
Minimal evaluation: define capabilities, ingest telemetry, query machine state.

Run from the repo root::

    PYTHONPATH=src python examples/01_minimal/evaluate.py
"""

from __future__ import annotations

from datetime import datetime, timezone

from sense_ai import (
    ALL,
    Equals,
    Gte,
    Fresh,
    ContextMachine,
    TelemetryObservation,
    capability,
)


# ── 1. Capability definitions ─────────────────────────────────────────────────

@capability(name="battery.operational", version="1.0")
def battery_operational(c: ContextMachine) -> bool:
    """
    Battery is present and above the safe depletion threshold.
    Raises UNAVAILABLE if the sensor is absent; DEGRADED if the reading
    is low but the battery is still present.
    """
    level = c.observe("battery.charge_level")
    present = c.observe("battery.present")

    if not present.is_available:
        return False
    if level.value is None or level.value < 10:
        return False
    if level.value < 20:
        # Warn but do not block
        c.warn("Battery level critically low", path="battery.charge_level")
    return True


@capability(name="motor.operational", version="1.0")
def motor_operational(c: ContextMachine) -> bool:
    """
    Motor controller reports no active faults and speed is within safe bounds.
    """
    faults = c.observe("motor.active_faults")
    speed = c.observe("motor.speed_rpm")
    temp = c.observe("motor.winding_temp_c")

    # Must have no active faults
    if faults.value not in (None, 0, []):
        return False

    # Speed must be within safe operating range
    if not (0 <= (speed.value or -1) <= 5000):
        return False

    # Temperature must be within thermal limits
    if (temp.value or 0) > 90:
        c.warn("Motor winding temperature elevated", path="motor.winding_temp_c")
        return False
    return True


@capability(name="network.connectivity", version="1.0")
def network_connectivity(c: ContextMachine) -> bool:
    """
    Network adapter is connected with acceptable latency.
    """
    connected = c.observe("network.connected")
    latency_ms = c.observe("network.latency_ms")

    if not connected.is_available:
        return False
    if (latency_ms.value or 999) > 500:
        c.warn("High network latency", path="network.latency_ms")
        return False
    return True


# ── 2. Ingest telemetry ───────────────────────────────────────────────────────

def ingest(machine: ContextMachine) -> None:
    """Simulate telemetry ingestion from a sensor/API."""
    now = datetime.now(timezone.utc)

    observations = [
        # Battery
        TelemetryObservation(path="battery.present",      value=True,   observed_at=now, source="bms", ttl_ms=5000),
        TelemetryObservation(path="battery.charge_level",  value=17.3,  observed_at=now, source="bms", ttl_ms=2000),
        # Motor
        TelemetryObservation(path="motor.active_faults",   value=0,     observed_at=now, source="mcu", ttl_ms=5000),
        TelemetryObservation(path="motor.speed_rpm",       value=1200,  observed_at=now, source="mcu", ttl_ms=1000),
        TelemetryObservation(path="motor.winding_temp_c",  value=72.0,  observed_at=now, source="mcu", ttl_ms=3000),
        # Network
        TelemetryObservation(path="network.connected",     value=True,  observed_at=now, source="nm",  ttl_ms=10000),
        TelemetryObservation(path="network.latency_ms",    value=42.0,  observed_at=now, source="nm",  ttl_ms=2000),
    ]

    for obs in observations:
        machine.observe(obs)


# ── 3. Run evaluation ────────────────────────────────────────────────────────

def main() -> None:
    machine = ContextMachine(machine_ref="unit-001")

    # Register capabilities
    machine.define_capability(battery_operational)
    machine.define_capability(motor_operational)
    machine.define_capability(network_connectivity)

    # Ingest telemetry (normally from an adapter)
    ingest(machine)

    # Individual capability evaluation
    print("=== Individual evaluations ===")
    for cap_name in ["battery.operational", "motor.operational", "network.connectivity"]:
        result = machine.evaluate(cap_name)
        print(f"  {cap_name}: {result.status.name}  (blocking={result.blocking})")
        for warning in result.warnings:
            print(f"    !  {warning}")
        if result.status.name == "UNAVAILABLE":
            for violation in result.blocking:
                print(f"    X  {violation.path}: {violation.constraint_name}  actual={violation.observed}")

    # Full snapshot
    print("\n=== Full snapshot ===")
    snap = machine.snapshot()
    print(f"  Machine ref : {snap.machine_ref}")
    print(f"  Schema ver  : {snap.schema_version}")
    print(f"  Observations: {len(snap.observations)} fields")
    print(f"  Capabilities : {len(snap.capabilities)} defined")

    for cap_snap in snap.capabilities.values():
        status = cap_snap.status.name
        marker = "OK" if status == "AVAILABLE" else ("WARN" if status == "DEGRADED" else "FAIL")
        print(f"    [{marker}]  {cap_snap.name}  ->  {status}")

    # Transition detection
    print("\n=== Transition log (last 5) ===")
    for t in machine.transitions()[-5:]:
        prev = t.previous.name if t.previous else "NONE"
        print(f"  {t.at.isoformat()}  {prev} -> {t.current.name}  ({t.capability})")

    # Batch evaluation with constraint expressions
    print("\n=== Batch constraint: motor OK + battery OK ===")
    batch = machine.evaluate_all()
    all_pass = all(r.status.name == "AVAILABLE" for r in batch.values())
    print(f"  All capabilities AVAILABLE: {all_pass}")
    for name, result in batch.items():
        if result.status.name != "AVAILABLE":
            print(f"    X  {name}: {result.status.name}")


if __name__ == "__main__":
    main()
