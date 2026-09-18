# Sense Quickstart

This quickstart covers the complete path from raw device data to current machine capability.

## Install

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense
pip install -e ".[dev]"
```

## 1. Define canonical telemetry and raw mappings

```python
from sense_ai import SenseConfig

config = SenseConfig.from_dict(
    {
        "telemetry": {
            "schema": {
                "strict": True,
                "fields": [
                    {
                        "path": "battery.level_pct",
                        "kind": "number",
                        "minimum": 0,
                        "maximum": 100,
                        "ttl_ms": 5000,
                    },
                    {
                        "path": "safety.estop",
                        "kind": "boolean",
                        "ttl_ms": 1000,
                    },
                ],
            },
            "mappings": [
                {
                    "source": "battery.ratio",
                    "target": "battery.level_pct",
                    "transform": "ratio_to_percent",
                    "required": True,
                },
                {
                    "source": "estop",
                    "target": "safety.estop",
                    "required": True,
                },
            ],
        },
        "capabilities": [
            {
                "name": "machine.ready",
                "version": "1.0.0",
                "requires": [
                    {
                        "op": "gte",
                        "path": "battery.level_pct",
                        "value": 20,
                    },
                    {
                        "op": "equals",
                        "path": "safety.estop",
                        "value": False,
                    },
                ],
            }
        ],
    }
)
```

## 2. Build a machine

```python
machine = config.build_machine(machine_ref="robot-001")
```

## 3. Ingest raw telemetry

```python
ingestion = machine.ingest(
    {
        "battery": {"ratio": 0.74},
        "estop": False,
    },
    normalizer=config.normalizer,
)

print(ingestion.ok)
```

Sense converts `0.74` into the canonical:

```text
battery.level_pct = 74.0
```

## 4. Evaluate current capability

```python
result = machine.evaluate("machine.ready")

print(result.status.value)

for reason in result.reasons:
    print(reason.code, reason.path)
```

Possible states:

- `AVAILABLE` — valid/fresh evidence and mandatory rules pass.
- `DEGRADED` — mandatory rules pass, but a degradation condition is active.
- `UNAVAILABLE` — valid evidence proves a mandatory rule fails.
- `UNKNOWN` — evidence is missing, stale, invalid, or evaluation failed.

## 5. Observe invalid evidence

```python
machine.observe("battery.level_pct", "high")

result = machine.evaluate("machine.ready")

assert result.status.value == "UNKNOWN"
assert result.blocking[0].is_invalid
```

Sense does not confuse malformed telemetry with a physical machine failure.

## 6. Watch transitions

```python
@machine.on_transition("machine.ready")
def on_change(transition):
    print(transition.label)
    print(transition.reasons)
```

Transitions only emit when status changes.

## 7. Create a privacy-safe snapshot

```python
snapshot = machine.snapshot()

public = snapshot.publishable_view()
assert public.observations == {}
```

Explicitly allow selected observations only when needed:

```python
public = snapshot.publishable_view(
    keep_observations=["battery.level_pct"],
)
```

## 8. Use a transport adapter

The same `TelemetryNormalizer` works with replay, ROS 2, MQTT, HTTP, or an OEM-specific adapter.

### Replay

```python
from sense_ai import ReplayAdapter, ReplayFrame

ReplayAdapter(
    machine,
    config.normalizer,
    [
        ReplayFrame(
            {
                "battery": {"ratio": 0.80},
                "estop": False,
            }
        )
    ],
).run()
```

### ROS 2

Install:

```bash
pip install -e packages/Sense-ros2
```

See [sense-ros2](packages/Sense-ros2/README.md).

### MQTT

```bash
pip install -e packages/Sense-mqtt
```

See [sense-mqtt](packages/Sense-mqtt/README.md).

### HTTP

```bash
pip install -e packages/Sense-http
```

See [sense-http](packages/Sense-http/README.md).

## 9. Optional peaq Activity Event

Install:

```bash
pip install -e packages/Sense-peaq
```

Then:

```python
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqEventPublisher

client = PeaqosClient.from_env()
publisher = PeaqEventPublisher(client, machine_id=42)

transition = machine.last_transition("machine.ready")

if transition is not None:
    receipt = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
    )
    print(receipt.tx_hash)
```

The default event is self-reported/off-chain. Higher provenance requires real supporting evidence.

For a real network verification flow, see [tests/live/README.md](tests/live/README.md).

## 10. Machine Markets runtime gating

```python
from sense_peaq import check_market_eligibility

eligibility = check_market_eligibility(
    machine.snapshot(),
    ["machine.ready"],
)

print(eligibility.eligible)
```

This stays local and does not invent peaq market fields.

## Next

- [Complete pipeline example](examples/06_full_pipeline/README.md)
- [Capability guide](docs/Capability-Guide.md)
- [Compatibility](docs/Compatibility.md)
- [Security](SECURITY.md)
