# Sense

**Sense** is a local-first Python SDK that turns live physical machine telemetry into structured, explainable **current capability context**.

It answers questions such as:

> Can this machine perform `warehouse.pick` right now, and if not, why?

Sense evaluates locally. Network integrations are optional.

```text
raw telemetry
    ↓
normalized observations
    ↓
freshness + constraints
    ↓
current capability
    ↓
AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
    ↓
explainable transition
    ↓
optional peaq Activity Event / Machine Markets context
```

## Status

Sense is currently **pre-1.0**. The public API is usable, but still evolving while the peaq and ROS 2 integrations mature.

Current package version: **0.2.0**

## What Sense is

Sense provides:

- a local machine observation store;
- timestamp and freshness handling;
- deterministic capability rules;
- explicit `AVAILABLE`, `DEGRADED`, `UNAVAILABLE`, and `UNKNOWN` states;
- machine-readable reasons for failed constraints;
- capability transition detection;
- a versioned JSON context schema;
- privacy controls for external snapshots;
- optional peaq and ROS 2 adapters.

Sense is **not** a motion planner, robot controller, safety-certification system, world model, fleet manager, or replacement for ROS 2 or peaqOS.

## Install from this repository

Python 3.10+ is required.

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense

python -m venv .venv
source .venv/bin/activate

pip install -e .
```

Development dependencies:

```bash
pip install -e ".[dev]"
```

peaq adapter:

```bash
pip install -e packages/Sense-peaq
```

ROS 2 adapter:

```bash
pip install -e packages/Sense-ros2
```

## Quick example

```python
from datetime import datetime, timezone

from sense_ai import ContextMachine, capability, equals, fresh, gte

machine = ContextMachine(machine_ref="robot-001")

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

machine.observe("tool.gripper.available", True)
machine.observe("safety.estop", False)
machine.observe("battery.level_pct", 72)
machine.observe(
    "localization.pose",
    {"x": 1.4, "y": 3.2, "yaw": 0.2},
    observed_at=datetime.now(timezone.utc),
    ttl_ms=1500,
)
machine.observe("payload.utilization_pct", 42)

result = machine.evaluate("warehouse.pick")

print(result.status)
for reason in result.reasons:
    print(reason.code, reason.path, reason.observed)
```

## Capability states

| State | Meaning |
|---|---|
| `AVAILABLE` | Required evidence is present and mandatory constraints pass. |
| `DEGRADED` | Mandatory constraints pass, but a configured degradation condition is active. |
| `UNAVAILABLE` | A mandatory constraint has a concrete failing value. |
| `UNKNOWN` | Required evidence is missing or too stale to make a safe conclusion. |

`UNKNOWN` must never be treated as `AVAILABLE`.

## Freshness

Freshness is time-dependent. Sense re-evaluates capabilities whenever a snapshot is requested, even if no new telemetry has arrived.

```python
machine.define_capability(
    capability(
        "navigation.ready",
        requires=[fresh("localization.pose", max_age_ms=1000)],
    )
)
```

`observed_at` records when the source measured a value. `received_at` records when Sense received it.

`ttl_ms` is source validity metadata. `fresh(...)` is the capability-specific freshness requirement.

## Structured telemetry

Observation values can be any JSON-compatible value:

```python
machine.observe(
    "localization.pose",
    {
        "position": {"x": 1.0, "y": 2.0, "z": 0.0},
        "covariance": [0.01, 0.02, 0.03],
    },
)
```

Use `machine.get_observation(path)` to read state. The older `machine.observe(path)` read form remains available for compatibility.

## Snapshots and privacy

```python
snapshot = machine.snapshot()
print(snapshot.to_json(indent=2))
```

Raw telemetry remains local by default.

For an external view:

```python
public = snapshot.publishable_view()
```

`publishable_view()` includes capability results but **no raw observations by default**.

Explicitly allow observations when needed:

```python
public = snapshot.publishable_view(
    keep_observations=["battery.*"],
)
```

## Transitions

```python
@machine.on_transition("warehouse.pick")
def on_pick_transition(transition):
    print(transition.label)
    print(transition.reasons)
```

A transition is emitted only when the capability state changes.

## Evidence quality

Sense includes an optional local evidence-quality helper:

```python
from sense_ai import compute_evidence_quality

snapshot = machine.snapshot()

report = compute_evidence_quality(
    schema_version=snapshot.schema_version,
    machine_id=snapshot.machine_ref or "",
    observations=list(snapshot.observations.values()),
)

print(report.quality_band)
print(report.overall_score)
```

This score describes **telemetry evidence quality**. It is not a machine trust score and is not the same thing as peaq event trust levels.

The previous `compute_trust_report` name remains as a compatibility alias.

## peaq integration

Sense uses the official peaqOS Python SDK.

peaq documentation:

- https://docs.peaq.xyz/peaqos/install
- https://docs.peaq.xyz/peaqos/concepts/events
- https://docs.peaq.xyz/peaqos/concepts/machine-markets
- https://docs.peaq.xyz/peaqos/sdk-reference/sdk-python
- https://docs.peaq.xyz/peaqos/sdk-reference/orchestration-py

Install the adapter:

```bash
pip install -e packages/Sense-peaq
```

The adapter depends on `peaq-os-sdk>=0.4.0`.

### Publish a capability transition

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
    receipt = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
    )
    print(receipt.tx_hash)
```

Sense publishes selected capability transitions as **peaq Activity Events**. It delegates hashing, signing, validation and transaction submission to the official peaqOS SDK.

For locally derived machine context, the adapter defaults to peaq trust level `0` (self-reported) and source chain `0` (off-chain). Do not raise those values unless the event actually satisfies peaq's documented provenance requirements.

### Machine Markets

Sense does not implement its own marketplace.

`MachineMarketsAdapter` is a thin wrapper around the official `client.orchestration` surface.

```python
from sense_peaq import MachineMarketsAdapter, to_market_context

markets = MachineMarketsAdapter(client)

machines = markets.list_machines(limit=20)
services = markets.list_market_services(limit=20)

runtime_context = to_market_context(machine.snapshot())
```

Use request types from `peaq-os-sdk` when calling `search_market`. Sense does not invent peaq market fields.

## ROS 2

The ROS 2 package is currently an early adapter around `rclpy`.

See [packages/Sense-ros2/README.md](packages/Sense-ros2/README.md).

Sense does not replace peaq's own ROS 2 runtime.

## Schema

The language-neutral context schema is:

```text
schemas/context-1.0.schema.json
```

Schema versions are independent from Python package versions.

## Repository layout

```text
src/sense_ai/              core SDK
schemas/                   versioned context schema
packages/Sense-peaq/       peaqOS adapter
packages/Sense-ros2/       ROS 2 adapter
examples/                  runnable examples
tests/unit/                core unit tests
tests/contract/            schema contract tests
tests/integration/         lifecycle integration tests
tests/e2e/                 end-to-end tests
```

## Development

```bash
ruff check src/ packages/
ruff format --check src/ packages/
mypy src/
pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v

pip install -e packages/Sense-peaq
pytest tests/e2e/ -v

python -m build
```

CI runs these checks for pull requests.

## Security

Sense does not automatically upload telemetry and does not manage peaq private keys.

See [SECURITY.md](SECURITY.md).

## Documentation

- [Quickstart](QUICKSTART.md)
- [Capability guide](docs/Capability-Guide.md)
- [peaq adapter](packages/Sense-peaq/README.md)
- [ROS 2 adapter](packages/Sense-ros2/README.md)
- [Contributing](CONTRIBUTING.md)

## License

Apache-2.0.
