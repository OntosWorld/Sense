# Example 02 — Evaluation with Rules

This example demonstrates declarative rule-based capability evaluation using Sense's built-in constraint primitives and logical composition operators.

**Run from the repo root:**

```bash
PYTHONPATH=src python examples/02_with_rules/evaluate.py
```

## What it does

1. Defines four capabilities using rule expressions:
   - `inspection.ready` — battery, estop, gripper fault code, freshness, mode validation
   - `perception.available` — sensor availability with `ANY` and `ONLY_ONE` (XOR)
   - `operation.enabled` — mode enforcement with `NOT` and `ANY`
   - `diagnostics.clear` — fault code exclusion with `NONE_OF`
2. Runs three scenarios: **healthy**, **degraded** (low battery), and **unavailable** (estop engaged)
3. Inspects `ConstraintOutcome` objects to see pass/fail codes, observed values, and staleness flags

## Key concepts

### Rule primitives

```python
from sense_ai import equals, gte, lt, exists, fresh, in_

machine.define_capability(
    capability(
        "my.capability",
        requires=[
            equals("path", expected_value),
            gte("path", threshold),
            lt("path", threshold),
            exists("path"),
            fresh("path", max_age_ms=2000),
            in_("path", ["value_a", "value_b"]),
        ],
    )
)
```

### Logical composition

```python
from sense_ai import ALL, ANY, NOT, NONE_OF, ONLY_ONE

machine.define_capability(
    capability(
        "my.capability",
        requires=[
            # All must pass (AND)
            ALL(constraint_a, constraint_b),
            # At least one must pass (OR)
            ANY(constraint_c, constraint_d),
            # None may pass (NOR)
            NONE_OF(constraint_e, constraint_f),
            # Exactly one must pass (XOR)
            ONLY_ONE(constraint_g, constraint_h),
            # Negation
            NOT(equals("mode.current", "maintenance")),
        ],
    )
)
```

### Severity and naming

```python
fresh("pose", max_age_ms=1000, name="localisation-stale", severity="warning")
# → result.warnings contains this if it fails, not result.blocking
```

### ConstraintOutcome inspection

```python
result = machine.evaluate("inspection.ready")
for outcome in result.outcomes:
    print(f"{outcome.code}  path={outcome.path}  passed={outcome.passed}  stale={outcome.is_stale}")
```
