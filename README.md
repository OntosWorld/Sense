# Sense AI SDK

**Sense** is a local-first Python SDK that converts raw physical machine telemetry into structured, explainable current capability and constraint context, and allows developers to connect selected context to peaq.

## Status

| | |
|---|---|
| CI gates | ✅ 9/9 | lint, type check, unit, contract, integration, schema-validation, build, format, security |
| Phases | Phase 1 + 2 core shipped |
| Test layers | unit · contract · integration · e2e |

## What it does

```
Telemetry → observe() → ContextMachine → evaluate() → CapabilityResult + ContextSnapshot
                                                        ↓
                                               compute_trust_report()
                                                        ↓
                                               PeaqContextPublisher.publish()
```

1. **Observe** — ingest raw telemetry (sensor readings, actuator states, system metrics)
2. **Define** — declare what combinations of telemetry mean a machine *can* do something
3. **Evaluate** — get a deterministic status: `AVAILABLE` / `DEGRADED` / `UNAVAILABLE` / `UNKNOWN`
4. **Trust** — run the trust engine for a trustworthiness verdict alongside every evaluation
5. **Publish** — optionally push to peaq for on-chain capability attestation

## Installation

```bash
# Core SDK
pip install sense-ai

# Core + peaq adapter (on-chain publishing)
pip install sense-ai[peaq]

# Core + ROS 2 adapter
pip install sense-ai[ros2]

# All packages + dev tools
pip install -e ".[dev]"
```

Requires Python 3.10+.

## Core API

```python
from sense_ai import (
    ContextMachine, capability, TelemetryObservation,
    equals, gte, fresh,
)

machine = ContextMachine(
    machine_ref="drone-001",
    peaq_did="did:peaq:0x...",   # optional — required only for on-chain publishing
)

# Define what "delivery.ready" means
machine.define_capability(
    capability(
        "delivery.ready",
        requires=[
            equals("tool.gripper.available", True),
            equals("safety.estop", False),
            gte("battery.level_pct", 30),
            fresh("localization.pose", max_age_ms=1000),
        ],
        degrade_when=[
            gte("payload.utilization_pct", 90),
        ],
    )
)

# Ingest telemetry
machine.observe(TelemetryObservation(
    path="battery.level_pct",
    value=72,
    observed_at=datetime.now(timezone.utc),
    source="bms",
    ttl_ms=5000,
))

# Evaluate — returns CapabilityResult
result = machine.evaluate("delivery.ready")
print(result.status)    # AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
print(result.reasons)  # human-readable list of what passed / failed

# Snapshot for publishing or trust evaluation
snapshot = machine.snapshot()
```

### Rule primitives

| Rule | Meaning |
|------|---------|
| `equals(path, value)` | Exact value match |
| `gte(path, n)`, `gt`, `lt`, `lte` | Numeric comparisons |
| `in_(path, [a, b])` | Value in set |
| `exists(path)` | Any value present |
| `fresh(path, max_age_ms)` | Not older than `max_age_ms` |
| `ALL(...)`, `ANY(...)`, `NOT(...)`, `NONE_OF(...)`, `ONLY_ONE(...)` | Logical composition |

### Trust engine

```python
from sense_ai.trust import compute_trust_report

report = compute_trust_report(situation=snapshot)
print(report.quality_band)    # TRUSTWORTHY | UNCERTAIN | UNTRUSTWORTHY
print(report.overall_score)   # 0.0–1.0
for dim in report.dimensions:
    print(f"  {dim.name}: {dim.score:.2f} (weight {dim.weight})")
```

The trust engine is pure and deterministic — no network dependencies.

### Data minimisation

Before publishing, strip sensitive telemetry:

```python
# Keep only specific observation paths
pub = snapshot.redact(keep_observations=["battery.*", "sensor.*"])

# Strip peaq_did and keep everything for internal use
local = snapshot.local_view()

# Pre-configured safe view for external publication
public = snapshot.publishable_view()
```

## Adapters

### peaq (on-chain publishing)

```python
from sense_peaq import PeaqContextPublisher, to_market_context

publisher = PeaqContextPublisher(
    rpc_endpoint="https://api.peaq.network",
    peaq_client=my_peaq_client,   # supply your own peaqOS client instance
)

result = publisher.publish(snapshot)
print(result.tx_hash)    # on-chain transaction hash
```

`to_market_context()` builds a Machine Markets listing from the same snapshot. See [`packages/Sense-peaq/`](packages/Sense-peaq/) for full documentation.

### ROS 2

```python
from sense_ros2 import ROS2ContextClient

client = ROS2ContextClient(
    node_name="sense_node",
    topic_map={"battery_level": "battery.level_pct"},
)
client.start(machine)

# Telemetry from ROS 2 topics flows into the machine automatically
result = machine.evaluate("delivery.ready")
```

See [`packages/Sense-ros2/`](packages/Sense-ros2/) for full documentation.

## Directory layout

```
src/sense_ai/          Core SDK
  model/               Domain types (ContextMachine, TelemetryObservation, etc.)
  rules/               Rule primitives and composition
  events/              Event bus and typed events
  trust/               Trust engine
  serialization/       JSON Schema validation
  adapters/            Built-in adapters
  errors.py            Typed error hierarchy (FR-14)

packages/
  Sense-peaq/          peaq on-chain adapter
  Sense-ros2/          ROS 2 integration

schemas/               JSON Schema definitions (language-neutral)

tests/
  unit/                Unit tests
  contract/            Schema contract tests
  integration/         Adapter / machine lifecycle integration tests
  e2e/                 End-to-end pipeline tests

examples/
  01_minimal/          Minimal evaluation
  02_with_rules/       Rules + logical composition
  03_with_trust/       Trust engine
  04_peaq/             peaq publishing
  05_ros2/             ROS 2 integration
```

## Running tests

```bash
# All tests
pytest tests/ -v

# By layer
pytest tests/unit/       # unit tests
pytest tests/contract/   # schema contract tests
pytest tests/integration/  # integration tests
pytest tests/e2e/       # end-to-end tests

# With coverage
pytest tests/unit/ --cov=sense_ai --cov-report=term-missing
```

## Full quickstart

See [QUICKSTART.md](QUICKSTART.md) for a step-by-step guide covering install → create → observe → evaluate → trust → publish.

## Security

See [SECURITY.md](SECURITY.md) for guidance on private key handling, ROS 2 topic ACLs, secrets injection, and data minimisation.
