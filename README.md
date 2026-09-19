# Sense

**Sense** is a local-first Python SDK that turns raw physical-machine telemetry into validated, normalized, explainable **current capability context**.

```text
raw machine telemetry
        ↓
validation
        ↓
normalization / unit transforms
        ↓
canonical Sense observations
        ↓
freshness + constraints
        ↓
AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
        ↓
structured reasons + transitions
        ↓
privacy-safe context
        ↓
optional ROS 2 / MQTT / HTTP / peaq integrations
```

Sense answers:

> What can this machine actually do right now, why, and how reliable is the evidence behind that answer?

## Status

Current pre-1.0 release: **0.3.0**

The public API is usable, but pre-1.0 while adapter and ecosystem integration matures.

## What Sense provides

- canonical telemetry schemas;
- raw-payload validation;
- deterministic normalization and unit transforms;
- JSON-compatible structured observations;
- separate `observed_at` and `received_at`;
- source TTL and capability-specific freshness;
- reusable, versioned capability definitions;
- `AVAILABLE`, `DEGRADED`, `UNAVAILABLE`, and `UNKNOWN`;
- invalid, missing, and stale evidence → `UNKNOWN`;
- nested explanations for composed rules;
- meaningful state transitions;
- versioned language-neutral snapshots;
- privacy-safe publication views;
- replay/simulator ingestion;
- ROS 2, MQTT, and HTTP telemetry adapters;
- official peaqOS Activity Event and Machine Markets integration.

Sense is **not** a robot controller, planner, safety-certification system, world model, fleet manager, machine identity system, or replacement for ROS 2 or peaqOS.

## Install

Core:

```bash
pip install sense-ai
```

From this repository:

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense
pip install -e ".[dev]"
```

Optional adapters:

```bash
pip install sense-peaq
pip install sense-ros2
pip install sense-mqtt
pip install sense-http
```

Repository development installs:

```bash
pip install -e packages/Sense-peaq
pip install -e packages/Sense-ros2
pip install -e packages/Sense-mqtt
pip install -e packages/Sense-http
```

Python 3.10+ is supported.

## Fast peaq verification

If your peaq wallet/client is already configured using the normal peaqOS SDK
environment, live verification is one command:

```bash
sense-peaq verify-live --machine-id 42
```

Or set the machine ID once:

```bash
export SENSE_PEAQ_MACHINE_ID=42
sense-peaq verify-live
```

The command:

```text
load user's peaq configuration
        ↓
create PeaqosClient
        ↓
show wallet / network / machine ID
        ↓
build a Sense capability transition
        ↓
local preflight
        ↓
ask before spending gas
        ↓
submit real peaq Activity Event
        ↓
print transaction hash + data hash
```

Sense does **not** accept a private key as a CLI argument and does not manage
wallet custody. The user configures their wallet through the official peaqOS
SDK; Sense receives the configured client.

For a completely fresh local test environment, including a throwaway wallet,
dependency setup, balance check, machine ID prompt, wallet-free tests, and the
same live verification command:

```bash
git clone --branch fix/sdk-alignment-peaq --single-branch https://github.com/OntosWorld/Sense.git \
  && cd Sense \
  && bash scripts/peaq-live-test.sh
```

The helper pauses only when you need to fund the displayed test wallet and enter
the machine ID.

See [QUICKSTART.md](QUICKSTART.md) for the full SDK path.

## Complete configured pipeline

A single configuration can define canonical telemetry, raw mappings, transforms, and reusable capabilities:

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
                        "unit": "percent",
                    }
                ],
            },
            "mappings": [
                {
                    "source": "battery.ratio",
                    "target": "battery.level_pct",
                    "transform": "ratio_to_percent",
                    "required": True,
                }
            ],
        },
        "capabilities": [
            {
                "name": "power.ready",
                "version": "1.0.0",
                "requires": [
                    {
                        "op": "gte",
                        "path": "battery.level_pct",
                        "value": 20,
                    }
                ],
            }
        ],
    }
)

machine = config.build_machine(machine_ref="robot-001")

machine.ingest(
    {"battery": {"ratio": 0.72}},
    normalizer=config.normalizer,
)

result = machine.evaluate("power.ready")
print(result.status.value)  # AVAILABLE
```

See [Example 06](examples/06_full_pipeline/README.md) for the full raw-device pipeline.

## Validation and UNKNOWN

Sense distinguishes physical failure from lack of valid evidence.

```text
battery = 8%, rule battery >= 20%
→ UNAVAILABLE

battery missing
→ UNKNOWN

battery stale
→ UNKNOWN

battery = "high" where a number is required
→ UNKNOWN

custom evaluator throws
→ UNKNOWN
```

This is a core invariant: **invalid evidence is not proof that a machine is unavailable.**

## Normalization

Built-in transforms include:

- `identity`
- `scale`
- `ratio_to_percent`
- `percent_to_ratio`
- `fahrenheit_to_celsius`
- `celsius_to_fahrenheit`
- `enum_map`
- `map_range`
- `round`

Custom transforms can be registered through `TransformRegistry`.

## Capability states

| State | Meaning |
|---|---|
| `AVAILABLE` | Required evidence is valid/fresh and mandatory constraints pass. |
| `DEGRADED` | Mandatory constraints pass, but a configured degraded condition is active. |
| `UNAVAILABLE` | A mandatory condition has a concrete failing value. |
| `UNKNOWN` | Required evidence is missing, stale, invalid, or evaluation failed. |

## Explainability

Simple and composed rules preserve structured evidence:

```python
result = machine.evaluate("warehouse.pick")

for reason in result.reasons:
    print(reason.code, reason.path)
    for child in reason.children:
        print("  ", child.code, child.path)
```

For `ALL`, `ANY`, `NOT`, `NONE_OF`, and `ONLY_ONE`, Sense keeps child outcomes so `unknown_paths` points to the actual missing/stale/invalid leaf evidence.

## Snapshots and privacy

```python
snapshot = machine.snapshot()
public = snapshot.publishable_view()
```

`publishable_view()` contains capability context but **no raw observations by default**.

Allow specific telemetry explicitly:

```python
public = snapshot.publishable_view(
    keep_observations=["battery.level_pct"],
)
```

The language-neutral schema is:

```text
schemas/context-1.0.schema.json
```

## Adapters

All transports feed the same validation/normalization pipeline.

### Replay / simulator

```python
from sense_ai import ReplayAdapter, ReplayFrame

ReplayAdapter(
    machine,
    config.normalizer,
    [ReplayFrame({"battery": {"ratio": 0.72}})],
).run()
```

### ROS 2

`sense-ros2` provides declarative topic → field → transform → Sense path mapping and preserves ROS source timestamps where available.

See [sense-ros2](packages/Sense-ros2/README.md).

### MQTT

`sense-mqtt` subscribes to JSON MQTT payloads and normalizes them before ingestion.

See [sense-mqtt](packages/Sense-mqtt/README.md).

### HTTP

`sense-http` polls JSON endpoints through the same canonical mapping layer.

See [sense-http](packages/Sense-http/README.md).

OEM-specific transports can implement the core `TelemetryAdapter` contract or feed `TelemetryNormalizer` directly.

## peaq integration

Sense uses the official `peaq-os-sdk>=0.8.0`.

### Activity Events

```python
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqEventPublisher

client = PeaqosClient.from_env()
publisher = PeaqEventPublisher(client, machine_id=42)

transition = machine.last_transition("warehouse.pick")
if transition is not None:
    receipt = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
    )
```

Default provenance is self-reported/off-chain:

```text
trust_level = 0
source_chain_id = 0
source_tx_hash = None
```

On-chain-verifiable provenance requires a real source transaction:

```python
from sense_peaq import EventProvenance

provenance = EventProvenance.onchain(
    source_chain_id=8453,
    source_tx_hash="0x...",
)
```

Sense currently rejects hardware-signed trust level 2 rather than claiming attestation it cannot prove.

### Machine Markets

Network operations delegate to `client.orchestration`.

Sense also provides local runtime gating:

```python
from sense_peaq import check_market_eligibility

eligibility = check_market_eligibility(
    machine.snapshot(),
    ["warehouse.pick"],
)
```

This lets an application use live physical state while leaving peaq's own market schemas untouched.

## Live peaq verification

Normal users do not need to run the repository test suite manually.

With the user's standard peaqOS wallet configuration already available:

```bash
sense-peaq verify-live --machine-id 42
```

This performs the client preflight, builds a real Sense capability transition,
asks for confirmation before the transaction, submits the Activity Event, and
prints the transaction and data hashes.

For CI/development, deterministic mocked peaq integration tests remain under
`tests/e2e/`, while the low-level opt-in network test remains under
`tests/live/`.

See [sense-peaq](packages/Sense-peaq/README.md) and
[tests/live/README.md](tests/live/README.md).

## Evidence quality

The optional `compute_evidence_quality()` helper describes telemetry evidence quality. It is not peaq trust, hardware attestation, machine credit, or a safety score.

## Repository layout

```text
src/sense_ai/                core SDK
  telemetry/                 schemas, transforms, normalization
  rules/                     deterministic constraints
  adapters/                  transport-neutral + replay
  registry.py                reusable capability registry
  config.py                  complete SDK config loader

packages/
  Sense-peaq/
  Sense-ros2/
  Sense-mqtt/
  Sense-http/

schemas/                     language-neutral context schema
examples/                    runnable examples
tests/                       unit, contract, integration, e2e, live
```

## Development

```bash
ruff check src/ packages/ tests/
ruff format --check src/ packages/ tests/
mypy -p sense_ai
pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v
pytest tests/e2e/ -v
python -m build
```

CI also tests and builds adapter packages.

## Compatibility and releases

See [Compatibility](docs/Compatibility.md), [Release guide](docs/Release.md), and [Changelog](CHANGELOG.md).

Releases use the workflow in `.github/workflows/release.yml`.

## Security

See [SECURITY.md](SECURITY.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Commits use Conventional Commits.

## License

Apache-2.0.
