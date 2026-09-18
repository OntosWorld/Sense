# Example 03 — Experimental Context Quality

> The folder keeps the historical name `03_with_trust`, but this example should be read as **context/evidence quality**, not machine trust.

This example demonstrates the optional deterministic quality heuristic exposed by `sense_ai.trust.compute_trust_report()`.

It is **not**:

- peaq event trust level;
- Machine Credit Rating;
- hardware attestation;
- a safety score;
- proof that a machine is trustworthy.

The core Sense capability engine does not require this module.

**Run from the repo root:**

```bash
PYTHONPATH=src python examples/03_with_trust/evaluate.py
```

## What it measures

The current heuristic looks at:

- freshness;
- required-path coverage;
- staleness;
- observation-path diversity.

It produces a local quality band and score that can be useful for diagnostics.

```python
from sense_ai.trust import compute_trust_report

snapshot = machine.snapshot()

report = compute_trust_report(
    schema_version=snapshot.schema_version,
    machine_id=snapshot.machine_ref or "",
    observations=list(snapshot.observations.values()),
)

print(report.quality_band)
print(report.overall_score)

for dimension in report.dimensions:
    print(dimension.name, dimension.score)
```

Do not use this score to override the capability status model. A capability with missing/stale mandatory evidence remains `UNKNOWN` regardless of the quality score.

Do not map this score to peaq's self-reported, on-chain-verifiable, or hardware-signed trust levels.
