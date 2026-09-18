# Sense Quickstart

This guide takes you from a clean checkout to a local capability evaluation and an optional peaq Activity Event.

## 1. Install

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense

python -m venv .venv
source .venv/bin/activate

pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## 2. Create a machine

```python
from sense_ai import ContextMachine

machine = ContextMachine(
    machine_ref="robot-001",
)
```

A `ContextMachine` holds the current observations and capability definitions for one physical machine.

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

`requires` are mandatory conditions.

`degrade_when` rules describe degraded conditions. If one is active while mandatory requirements still pass, the capability becomes `DEGRADED`.

## 4. Add telemetry

```python
from datetime import datetime, timezone

machine.observe("tool.gripper.available", True)
machine.observe("safety.estop", False)
machine.observe("battery.level_pct", 72)
machine.observe(
    "localization.pose",
    {
        "x": 1.0,
        "y": 2.0,
        "yaw": 0.15,
    },
    observed_at=datetime.now(timezone.utc),
    ttl_ms=1500,
    source="localization",
)
machine.observe("payload.utilization_pct", 42)
```

Sense supports JSON-compatible values, including nested objects and arrays.

For transport-aware telemetry:

```python
from sense_ai import TelemetryObservation

observation = TelemetryObservation(
    path="battery.level_pct",
    value=72,
    observed_at=datetime.now(timezone.utc),
    received_at=datetime.now(timezone.utc),
    source="bms",
    ttl_ms=5000,
)

machine.observe(observation)
```

## 5. Evaluate

```python
result = machine.evaluate("warehouse.pick")

print(result.status)

for reason in result.reasons:
    print(
        reason.code,
        reason.path,
        reason.expected,
        reason.observed,
    )
```

Possible states:

| State | Meaning |
|---|---|
| `AVAILABLE` | Required evidence is known and mandatory conditions pass. |
| `DEGRADED` | Mandatory conditions pass, but a degradation condition is active. |
| `UNAVAILABLE` | A mandatory condition has a concrete failure. |
| `UNKNOWN` | Required evidence is missing or stale. |

Never treat `UNKNOWN` as `AVAILABLE`.

## 6. Read current state

Use:

```python
battery = machine.get_observation("battery.level_pct")

if battery is not None:
    print(battery.value)
    print(battery.age_ms)
```

The older `machine.observe("battery.level_pct")` read form remains available for backward compatibility, but `get_observation()` is clearer.

## 7. Create a snapshot

```python
snapshot = machine.snapshot()

print(snapshot.to_json(indent=2))
```

Snapshots are always re-evaluated. This is important because telemetry can become stale even when no new observation arrives.

## 8. External/public snapshot

Raw telemetry remains local by default.

```python
public = snapshot.publishable_view()

assert public.observations == {}
```

Explicitly allow fields when required:

```python
public = snapshot.publishable_view(
    keep_observations=[
        "battery.level_pct",
    ],
)
```

## 9. Watch capability transitions

```python
@machine.on_transition("warehouse.pick")
def handle_transition(transition):
    print(transition.label)
    print(transition.reasons)
```

Now change machine state:

```python
machine.observe("battery.level_pct", 10)
machine.evaluate("warehouse.pick")
```

The transition becomes similar to:

```text
AVAILABLE → UNAVAILABLE
```

## 10. Optional evidence-quality report

```python
from sense_ai import compute_evidence_quality

snapshot = machine.snapshot()

quality = compute_evidence_quality(
    schema_version=snapshot.schema_version,
    machine_id=snapshot.machine_ref or "",
    observations=list(snapshot.observations.values()),
)

print(quality.quality_band)
print(quality.overall_score)
```

This is an **evidence-quality metric**, not a machine trust rating and not a peaq event trust level.

## 11. Optional peaq integration

Install:

```bash
pip install -e packages/Sense-peaq
```

The adapter uses the official `peaq-os-sdk>=0.4.0`.

Follow peaq's current environment configuration:

https://docs.peaq.xyz/peaqos/install

Then:

```python
from dotenv import load_dotenv
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqEventPublisher

load_dotenv()

client = PeaqosClient.from_env()

publisher = PeaqEventPublisher(
    client,
    machine_id=42,
)

transition = machine.last_transition("warehouse.pick")

if transition is not None:
    result = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
    )
    print(result.tx_hash)
    print(result.data_hash_hex)
```

Sense publishes the selected transition as a peaq **Activity Event**.

By default:

```text
trust_level = 0
source_chain_id = 0
```

because local physical context is self-reported/off-chain unless stronger provenance actually exists.

## 12. Machine Markets

Set `PEAQOS_ORCHESTRATION_URL` before creating the peaq client. peaq's canonical endpoint is currently documented as:

```text
https://orchestration.peaq.xyz
```

Then:

```python
from sense_peaq import MachineMarketsAdapter, to_market_context

markets = MachineMarketsAdapter(client)

machines = markets.list_machines(limit=20)
services = markets.list_market_services(limit=20)

sense_context = to_market_context(machine.snapshot())
```

For `search_market()`, construct the request using the types provided by the current `peaq-os-sdk`.

Sense does not create its own Machine Markets listing protocol.

## 13. Run tests

```bash
pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v

pip install -e packages/Sense-peaq
pytest tests/e2e/ -v

ruff check src/ packages/
ruff format --check src/ packages/
mypy -p sense_ai
```

## Next

- [Capability guide](docs/Capability-Guide.md)
- [peaq adapter](packages/Sense-peaq/README.md)
- [ROS 2 adapter](packages/Sense-ros2/README.md)
- [Security](SECURITY.md)
