# Example 01 — Minimal Evaluation

A minimal end-to-end example that defines capabilities, ingests telemetry, and evaluates machine state.

**Run from the repo root:**

```bash
pip install -e "."
PYTHONPATH=src python examples/01_minimal/evaluate.py
```

**What it does:**

1. Defines three capabilities — `battery.operational`, `motor.operational`, `network.connectivity` — using the `@capability` decorator.
2. Ingests simulated telemetry via `TelemetryObservation` objects.
3. Evaluates each capability individually, then produces a full snapshot.
4. Shows the transition log and batch evaluation result.

**Key concepts:**

- `ContextMachine` — holds telemetry observations and registered capabilities for one machine.
- `@capability` decorator — registers a Python callable as a capability evaluator.
- `TelemetryObservation` — a single telemetry reading with path, value, timestamp, source, and TTL.
- `ContextSnapshot` — the serialisable output of an evaluation, ready to publish or store.
- `ContextTransition` — records when a capability changed status between evaluations.

```python
from sense_ai import (
    ContextMachine,
    TelemetryObservation,
    capability,
)

@capability(name="battery.operational", version="1.0")
def battery_operational(c: ContextMachine) -> bool:
    level = c.observe("battery.charge_level")
    if level.value is None or level.value < 10:
        return False
    return True

machine = ContextMachine(machine_ref="unit-001")
machine.define_capability(battery_operational)
machine.observe(TelemetryObservation(
    path="battery.charge_level",
    value=50.0,
    observed_at=datetime.now(timezone.utc),
    source="bms",
    ttl_ms=5000,
))
result = machine.evaluate("battery.operational")
print(result.status)  # CapabilityStatus.AVAILABLE
```
