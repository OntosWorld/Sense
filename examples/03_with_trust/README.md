# Example 03 — Evidence Quality

This example demonstrates Sense's optional **evidence-quality** helper.

The helper summarizes freshness, coverage, staleness and observation diversity. It does **not** determine whether a machine is trustworthy and it is not a peaq event trust level.

Run:

```bash
pip install -e .
python examples/03_with_trust/evaluate.py
```

Example:

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

for dimension in report.dimensions:
    print(dimension.name, dimension.score)
```

The legacy `compute_trust_report` name remains available as a compatibility alias, but new code should use `compute_evidence_quality`.

Capability availability should still be determined by explicit capability rules, not by the evidence-quality score.
