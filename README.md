# Sense

**Sense** is a local-first Python SDK that turns live physical-machine telemetry into structured, explainable current capability.

```text
raw telemetry
    ↓
normalized observations
    ↓
freshness + constraints
    ↓
capability evaluation
    ↓
AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
    ↓
structured reasons + transitions
    ↓
optional peaq integration
```

Sense answers a runtime question that identity or marketplace metadata cannot answer on its own:

> **What can this machine actually do right now, and why?**

## Status

Sense is pre-1.0 software. The current package version is **0.2.0**.

The core evaluation engine is implemented and local-first. The peaq adapter is built against the official `peaq-os-sdk` Python surface. ROS 2 support is early and intentionally isolated from the core package.

## Core principles

- **Local first** — capability evaluation works without internet access.
- **Deterministic** — no hosted model, GPU, or probabilistic inference is required.
- **Explainable** — failed constraints and missing/stale evidence are structured.
- **Freshness-aware** — stale telemetry never silently remains available.
- **Privacy-first** — external publication excludes raw telemetry unless explicitly allowlisted.
- **Transport-neutral** — ROS 2, MQTT, HTTP, simulators, and OEM integrations belong in adapters.
- **peaq-compatible, not peaq-replacing** — Sense produces physical capability context; peaq provides machine identity, events, orchestration, markets, and economic infrastructure.

## Install

From source:

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense
pip install -e ".[dev]"
```

Core package:

```bash
pip install sense-ai
```

Optional peaq adapter from this repository:

```bash
pip install -e packages/Sense-peaq
```

Optional ROS 2 adapter:

```bash
pip install -e packages/Sense-ros2
```

Python 3.10+ is supported.

## Quick example

```python
from datetime import datetime, timezone

from sense_ai import ContextMachine, TelemetryObservation, capability, equals, fresh, gte

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

now = datetime.now(timezone.utc)

machine.observe("tool.gripper.available", True)
machine.observe("safety.estop", False)
machine.observe("battery.level_pct", 72)
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
machine.observe("payload.utilization_pct", 40)

result = machine.evaluate("warehouse.pick")

print(result.status.value)
print(result.blocking)
print(result.warnings)
print(result.unknown_paths)
```

## Capability states

| Status | Meaning |
|---|---|
| `AVAILABLE` | Required evidence exists, remains valid/fresh, and mandatory constraints pass. |
| `DEGRADED` | Mandatory constraints pass, but a developer-defined degradation condition is active. |
| `UNAVAILABLE` | A mandatory constraint fails with concrete evidence. |
| `UNKNOWN` | Required evidence is missing, invalid for evaluation, or stale. |

`UNKNOWN` is never treated as `AVAILABLE`.

## Freshness model

Each observation can carry its own `ttl_ms`. Once that TTL expires, rules treat the observation as stale.

A capability can impose a stricter requirement with `fresh(...)`:

```python
fresh("localization.pose", max_age_ms=1000)
```

The effective requirement is therefore conservative: the observation must still be valid under its own TTL and satisfy the capability-specific freshness rule.

Sense reevaluates capabilities whenever a snapshot is requested, because freshness can change even when no new telemetry arrives.

## Structured telemetry

Observation values may be JSON-compatible scalars, arrays, or objects.

```python
machine.observe(
    TelemetryObservation(
        path="localization.pose",
        value={
            "position": {"x": 1.2, "y": 0.4, "z": 0.0},
            "frame": "map",
        },
    )
)
```

Sense keeps `observed_at` and `received_at` separately so transport delay is not hidden.

## Transitions

Sense records meaningful capability-state changes.

```python
@machine.on_transition("warehouse.pick")
def handle(transition):
    print(transition.label)
    print(transition.to_dict())
```

Transitions include the structured reasons that produced the new state.

## Snapshots and privacy

```python
snapshot = machine.snapshot()
```

The canonical serialized format is versioned independently from the package and validated by `schemas/context-1.0.schema.json`.

For external publication:

```python
public = snapshot.publishable_view()
```

By default, `publishable_view()` keeps capability results but removes raw observations and the peaq DID.

To publish selected evidence:

```python
public = snapshot.publishable_view(
    keep_observations=["battery.*", "localization.status"],
)
```

## peaq integration

Sense uses the official peaqOS Python SDK.

Install peaq support:

```bash
pip install -e packages/Sense-peaq
```

### Activity Events

Meaningful Sense transitions can be submitted as peaq **Activity Events**:

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

Sense defaults to peaq's self-reported event trust level. It does not claim on-chain-verifiable or hardware-signed provenance automatically.

### Machine Markets

`MachineMarketsAdapter` delegates directly to the official `client.orchestration` namespace.

```python
from sense_peaq import MachineMarketsAdapter, to_market_context

markets = MachineMarketsAdapter(client)
services = markets.list_market_services(limit=20)

runtime_context = to_market_context(machine.snapshot())
```

Sense does not create its own listing registry. Runtime Sense context is intended to complement peaq's machine/service/orchestration data.

## ROS 2

The optional `sense-ros2` package currently provides a thin `rclpy` wrapper. Declarative topic-to-Sense mapping is still planned.

The core package does not require ROS 2.

## Context quality

An experimental deterministic context-quality module exists under `sense_ai.trust`. It evaluates evidence freshness/coverage heuristics. It is **not** peaq's trust level, Machine Credit Rating, hardware attestation, or a general statement that a machine is trustworthy.

It is not required for the core Sense pipeline.

## Repository layout

```text
src/sense_ai/              core SDK
packages/Sense-peaq/       official peaqOS adapter
packages/Sense-ros2/       ROS 2 adapter
schemas/                   language-neutral JSON Schema
tests/unit/                unit tests
tests/contract/            schema contract tests
tests/integration/         core integration tests
tests/e2e/                 end-to-end flows
examples/                  runnable examples
docs/                      developer guides
```

## Development

```bash
pip install -e ".[dev]"

ruff format src tests
ruff check src tests
mypy src
pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v
pytest tests/e2e/test_pipeline.py -v
python -m build
```

GitHub Actions also builds the distribution and performs an installation smoke test.

## Security

Sense does not upload telemetry automatically and the core SDK does not hold blockchain credentials.

See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Commits follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## License

Apache-2.0.
