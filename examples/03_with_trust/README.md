# Example 03 — Trust Evaluation

This example demonstrates how to run a trustworthiness evaluation alongside capability evaluation to produce a quality band and per-dimension scores.

**Run from the repo root:**

```bash
PYTHONPATH=src python examples/03_with_trust/evaluate.py
```

## What it does

1. Builds a `ContextMachine` with multiple capabilities
2. Runs three telemetry scenarios:
   - **Healthy** — all sensors reporting, recent observations
   - **Stale** — localisation pose is too old (freshness constraint fails)
   - **Sparse** — only a few sensors reporting (low coverage score)
3. Produces a `TrustReport` for each scenario via `compute_trust_report()`
4. Displays the quality band, overall score, observation count, and per-dimension breakdowns

## Key concepts

### TrustReport

```python
from sense_ai.trust import compute_trust_report

snapshot = machine.snapshot()
report = compute_trust_report(
    schema_version=snapshot.schema_version,
    machine_id=snapshot.machine_ref,
    observations=snapshot.observations,
)

print(report.quality_band)          # "excellent" | "good" | "fair" | "poor" | "critical"
print(report.overall_score)         # 0.0–1.0 float
print(report.observation_count)      # number of observations used
print(report.timestamp)             # datetime of computation

for dim in report.dimensions:
    print(f"  {dim.name}: {dim.score:.3f}  (weight={dim.weight})")
```

### Trust dimensions

| Dimension   | What it measures                                                     |
|-------------|----------------------------------------------------------------------|
| `freshness` | Observations are recent relative to their declared TTLs              |
| `coverage`  | A broad set of required observation paths is reporting                |
| `staleness` | No observations exceed the maximum-staleness threshold                |
| `diversity` | Observations span multiple sources and types (bonus dimension)        |

### When to use

Run `compute_trust_report()` alongside `machine.snapshot()` when you need to decide whether to act on the capability result — for example, before publishing to peaq or triggering an autonomous decision.

```python
snapshot = machine.snapshot()
trust = compute_trust_report(
    schema_version=snapshot.schema_version,
    machine_id=snapshot.machine_ref,
    observations=snapshot.observations,
)

if trust.quality_band in ("excellent", "good"):
    publisher.publish(snapshot)
else:
    print(f"Not publishing — quality_band={trust.quality_band}, score={trust.overall_score:.3f}")
```
