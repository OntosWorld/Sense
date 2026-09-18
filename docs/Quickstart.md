# Sense Quickstart

This guide takes you from raw telemetry to an explainable machine capability result.

## 1. Install

From the repository:

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense
pip install -e ".[dev]"
```

## 2. Create a machine

```python
from sense_ai import ContextMachine

machine = ContextMachine(machine_ref="robot-001")
```

A `ContextMachine` keeps the latest observation for each path and evaluates developer-defined capabilities locally.

## 3. Define a capability

```python
from sense_ai import capability, equals, fresh, gte

machine.define_capability(
    capability(
        "warehouse.pick",
        requires=[
            equals("tool.gripper.available", True),
            equals("safety.estop", False),
            gte("battery.level_pct", 20),
            fresh("localization.pose", max_age_ms=1000),
        ],
        degrade_when=[
            gte("payload.utilization_pct", 90),
        ],
    )
)
```

## 4. Ingest telemetry

```python
from datetime import datetime, timezone
from sense_ai import TelemetryObservation

now = datetime.now(timezone.utc)

machine.observe("tool.gripper.available", True)
machine.observe("safety.estop", False)
machine.observe("battery.level_pct", 78)
machine.observe("payload.utilization_pct", 40)

machine.observe(
    TelemetryObservation(
        path="localization.pose",
        value={"x": 1.2, "y": 0.4, "frame": "map"},
        observed_at=now,
        received_at=now,
        source="localization",
        ttl_ms=1000,
    )
)
```

Observation values may be any JSON-compatible scalar, list, or object.

`observed_at` is when the source measured the value. `received_at` is when Sense received it.

## 5. Evaluate

```python
result = machine.evaluate("warehouse.pick")

print(result.status.value)
print(result.blocking)
print(result.warnings)
print(result.unknown_paths)
```

The status is one of:

- `AVAILABLE` — required evidence is valid and mandatory rules pass.
- `DEGRADED` — mandatory rules pass but a degradation condition is active.
- `UNAVAILABLE` — a mandatory rule fails with concrete evidence.
- `UNKNOWN` — required evidence is missing or stale.

Sense never converts `UNKNOWN` into `AVAILABLE`.

## 6. Read observations explicitly

```python
battery = machine.get_observation("battery.level_pct")
```

For backward compatibility, `machine.observe("battery.level_pct")` can still read an existing observation, but new code should use `get_observation()`.

Passing an explicit `None` is a valid telemetry value:

```python
machine.observe("diagnostic.optional_value", None)
```

## 7. Handle transitions

```python
@machine.on_transition("warehouse.pick")
def on_change(transition):
    print(transition.label)
    print(transition.to_dict())
```

Transitions fire only when the capability status changes and include the structured reasons for the new state.

## 8. Create a snapshot

```python
snapshot = machine.snapshot()
print(snapshot.to_json())
```

Sense reevaluates capabilities on each snapshot request. This matters because telemetry can become stale even if no new observations arrive.

## 9. Publish safely

External publication is privacy-first:

```python
public = snapshot.publishable_view()
```

By default, raw observations are removed.

Explicitly allow evidence when needed:

```python
public = snapshot.publishable_view(
    keep_observations=["battery.*", "localization.status"],
)
```

## 10. Optional peaq Activity Event

Install the adapter:

```bash
pip install -e packages/Sense-peaq
```

Then use the official peaqOS client:

```python
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqContextPublisher

client = PeaqosClient.from_env()
publisher = PeaqContextPublisher(client, machine_id=123)

transition = machine.last_transition("warehouse.pick")
if transition:
    published = publisher.publish_transition(
        transition,
        machine_ref=machine.machine_ref,
    )
    print(published.tx_hash)
```

Sense uses a peaq Activity Event and defaults to the self-reported trust level. It does not turn locally-derived context into hardware attestation or on-chain-verifiable evidence automatically.

## 11. Machine Markets

Sense does not create a second marketplace.

```python
from sense_peaq import MachineMarketsAdapter, to_market_context

markets = MachineMarketsAdapter(client)
services = markets.list_market_services(limit=20)

runtime_context = to_market_context(machine.snapshot())
print(runtime_context.to_dict())
```

The network calls delegate to peaq's official `client.orchestration` API. Sense's runtime context remains a separate physical-state signal that your application can use alongside market results.

## Run tests

```bash
pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v
pytest tests/e2e/test_pipeline.py -v
```

See [Capability Guide](docs/Capability-Guide.md) for the rule and status model.
