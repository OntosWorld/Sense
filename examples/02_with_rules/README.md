# Example 02 — Evaluation with Rules

This example demonstrates declarative capability evaluation with Sense rule primitives and logical composition.

**Run from the repo root:**

```bash
PYTHONPATH=src python examples/02_with_rules/evaluate.py
```

## What it shows

- blocking requirements with `requires`;
- degradation conditions with `degrade_when`;
- comparison, existence, membership, and freshness rules;
- `ALL`, `ANY`, `NOT`, `NONE_OF`, and `ONLY_ONE`;
- structured failure reasons through `result.blocking` and `result.warnings`.

## Rule primitives

```python
from sense_ai import equals, exists, fresh, gte, in_, lt

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

## Logical composition

```python
from sense_ai import ALL, ANY, NONE_OF, NOT, ONLY_ONE

machine.define_capability(
    capability(
        "my.capability",
        requires=[
            ALL(constraint_a, constraint_b),
            ANY(constraint_c, constraint_d),
            NONE_OF(constraint_e, constraint_f),
            ONLY_ONE(constraint_g, constraint_h),
            NOT(equals("mode.current", "maintenance")),
        ],
    )
)
```

## Inspect reasons

```python
result = machine.evaluate("inspection.ready")

for reason in result.blocking + result.warnings:
    print(reason.code)
    print(reason.path)
    print(reason.expected)
    print(reason.observed)
    print(reason.observed_age_ms)
    print(reason.is_stale)
    print(reason.is_absent)
```

`blocking` and `warnings` contain failed/active conditions, not every successful rule evaluation.
