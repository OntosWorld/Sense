# Sense AI SDK — Quickstart

Get from installation to a working capability evaluation in under 5 minutes.

---

## 1. Install

```bash
# Core SDK only
pip install sense-ai

# Core + peaq adapter (on-chain publishing)
pip install sense-ai[peaq]

# Core + ROS 2 adapter
pip install sense-ai[ros2]

# All packages + dev tools
pip install -e ".[dev]"
```

Or install from source:

```bash
git clone https://github.com/your-org/sense-ai.git
cd sense-ai
pip install -e ".[dev]"
```

---

## 2. Create a machine

```python
from sense_ai import ContextMachine

machine = ContextMachine(
    machine_ref="drone-001",
    peaq_did="did:peaq:0x...",   # optional — needed only for on-chain publishing
)
```

A `ContextMachine` holds all telemetry observations and registered capabilities for one physical machine.

---

## 3. Define capabilities with typed rules

```python
from sense_ai import capability, equals, gte, fresh

machine.define_capability(
    capability(
        "delivery.ready",
        requires=[
            equals("tool.gripper.available", True),    # value must be True
            equals("safety.estop", False),              # value must be False
            gte("battery.level_pct", 30),             # numeric ≥ threshold
            fresh("localization.pose", max_age_ms=1000),  # no older than 1 second
        ],
        degrade_when=[
            gte("payload.utilization_pct", 90),        # triggers DEGRADED, not UNAVAILABLE
        ],
    )
)
```

Rule primitives available:

| Rule | Meaning |
|------|---------|
| `equals(path, value)` | Exact value match |
| `gte(path, n)`, `gt`, `lt`, `lte` | Numeric comparisons |
| `in_(path, [a, b])` | Value in set |
| `exists(path)` | Any value present |
| `fresh(path, max_age_ms)` | Not older than `max_age_ms` |
| `ALL(...)`, `ANY(...)`, `NOT(...)` | Logical composition |

---

## 4. Ingest telemetry

```python
from datetime import datetime, timezone
from sense_ai import TelemetryObservation

# Full object — for any value type
machine.observe(TelemetryObservation(
    path="battery.level_pct",
    value=72,
    observed_at=datetime.now(timezone.utc),
    source="bms",
    ttl_ms=5000,    # observation is valid for 5 seconds
))

# Shorthand for string / bool / number
machine.observe("tool.gripper.available", True)
machine.observe("safety.estop", False)
```

All telemetry is validated at the boundary and rejected with typed errors if malformed. Data stays local — nothing is sent over the network unless you explicitly publish.

---

## 5. Evaluate

```python
result = machine.evaluate("delivery.ready")
print(result.status)   # AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
print(result.reasons)  # human-readable list of what passed / failed
print(result.evidence) # which observations were used
print(result.evaluated_at)  # datetime of evaluation
```

`result` is a `CapabilityResult` — it is JSON-serialisable and contains everything needed for logging, debugging, or publishing.

---

## 6. Get a serialisable snapshot

```python
snapshot = machine.snapshot()
print(snapshot.model_dump_json(indent=2))
```

`ContextSnapshot` contains all capability statuses, the raw observations used, and metadata. It is the canonical input for the trust engine and the peaq adapter.

### Data minimisation

Before publishing, you can strip sensitive fields:

```python
redacted = snapshot.redact(keep_paths={"battery.level_pct", "delivery.ready"})
# Removes all paths except those explicitly listed

local_only = snapshot.local_view()
# Keeps everything — use for internal dashboards

public = snapshot.publishable_view()
# Keeps only capability names + statuses, no raw telemetry
```

---

## 7. Run the trust engine

The trust engine produces a trustworthiness verdict alongside the capability evaluation:

```python
from sense_ai.trust import compute_trust_report

report = compute_trust_report(situation=snapshot)
print(report.quality_band)    # TRUSTWORTHY | UNCERTAIN | UNTRUSTWORTHY
print(report.overall_score)   # 0.0–1.0
for dim in report.dimensions:
    print(f"  {dim.name}: {dim.score:.2f} (weight {dim.weight})")
print(f"Observations used: {report.observation_count}")
```

The trust engine is pure and deterministic — it runs entirely locally and has no network dependencies.

---

## 8. Subscribe to status transitions

React when a capability's status changes between evaluations:

```python
machine.on_transition(
    "delivery.ready",
    lambda t: print(f"[{t.timestamp}] delivery.ready: {t.previous_status} → {t.new_status}")
)

# Re-evaluate — triggers the callback only if status actually changed
machine.evaluate("delivery.ready")
```

---

## 9. Publish to peaq (optional)

Requires `pip install sense-ai[peaq]` and a pre-configured peaqOS client:

```python
from sense_peaq import PeaqContextPublisher, to_market_context

publisher = PeaqContextPublisher(
    rpc_endpoint="https://api.peaq.network",
    peaq_client=my_peaq_client,  # supply your own peaqOS client instance
)

result = publisher.publish(snapshot)
print(result.tx_hash)    # on-chain transaction hash
print(result.block_num)  # block number on confirmation

# Build a Machine Markets listing from the same snapshot
listing = to_market_context(
    snapshot,
    owner_did=machine.peaq_did,
    constraints=ListingConstraints(price_per_call_usd=0.001),
)
```

**No key custody.** The SDK never touches private keys. You supply an already-configured peaqOS client with the appropriate permissions.

---

## 10. Handle stale data

When an observation exceeds its TTL, the capability becomes `UNKNOWN` — no false positive is produced:

```python
import time

machine.observe("localization.pose", {"x": 1.0, "y": 2.0}, ttl_ms=1000)

result = machine.evaluate("delivery.ready")  # AVAILABLE — pose is fresh
time.sleep(1.5)                              # pose is now stale
result = machine.evaluate("delivery.ready")  # UNKNOWN — freshness rule fails
```

The `fresh(path, max_age_ms)` rule is the primary tool for staleness handling. Set TTL values on your observations to match your sensor update rate.

---

## Running the examples

```bash
git clone https://github.com/your-org/sense-ai.git
cd sense-ai
pip install -e "."

# Minimal evaluation
PYTHONPATH=src python examples/01_minimal/evaluate.py

# Rules + logical composition
PYTHONPATH=src python examples/02_with_rules/evaluate.py

# Trust engine
PYTHONPATH=src python examples/03_with_trust/evaluate.py

# peaq DID publishing
PYTHONPATH=src python examples/04_peaq/evaluate.py

# ROS 2 integration
PYTHONPATH=src python examples/05_ros2/evaluate.py
```

---

## Running the test suite

```bash
pytest tests/unit/          # unit tests — 95 tests
pytest tests/contract/      # schema contract tests — 16 tests
pytest tests/integration/   # integration tests — 34 tests
pytest tests/e2e/          # end-to-end tests
```

All 9 CI gates run automatically on every push. See the CI configuration in `.github/workflows/ci.yml`.

---

## Troubleshooting

**`ImportError: cannot import name 'ContextMachine'`**

Ensure `sense-ai` is installed and you are running from the correct Python environment:

```bash
pip show sense-ai
python -c "from sense_ai import ContextMachine; print('OK')"
```

**Capability returns `UNKNOWN` even though all values look correct**

Check two things:
1. The observation's `ttl_ms` — if it has expired since ingestion, the value is treated as absent.
2. The `fresh(path, max_age_ms)` rule — the observation must be younger than `max_age_ms` at evaluation time.

**peaq publish raises `PeaqConfigurationError`**

The `machine.peaq_did` must be set before calling `publish()`:

```python
machine = ContextMachine(machine_ref="robot-001", peaq_did="did:peaq:0x...")
```

---

## Next steps

- [API Reference](https://github.com/your-org/sense-ai) — full API documentation
- [`packages/Sense-peaq/README.md`](packages/Sense-peaq/README.md) — peaq adapter deep-dive
- [`packages/Sense-ros2/README.md`](packages/Sense-ros2/README.md) — ROS 2 adapter
- [`SECURITY.md`](SECURITY.md) — security policy and key-handling guidance
- [`examples/`](examples/) — runnable examples for every feature
