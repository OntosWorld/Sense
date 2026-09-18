# Capability Guide

Sense evaluates named physical-machine capabilities from current canonical observations.

## Status semantics

| Status | Meaning |
|---|---|
| `AVAILABLE` | Required evidence is valid/fresh and mandatory constraints pass. |
| `DEGRADED` | Mandatory constraints pass and a degradation condition is active. |
| `UNAVAILABLE` | Valid current evidence proves a mandatory condition fails. |
| `UNKNOWN` | Required evidence is missing, stale, invalid, or evaluation failed. |

`UNKNOWN` is never silently promoted to `AVAILABLE`.

## Define in Python

```python
from sense_ai import capability, equals, fresh, gte

spec = capability(
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

machine.define_capability(spec)
```

## Define declaratively

```python
from sense_ai import CapabilityRegistry

registry = CapabilityRegistry.from_dict(
    {
        "capabilities": [
            {
                "name": "warehouse.pick",
                "version": "1.0.0",
                "requires": [
                    {
                        "op": "gte",
                        "path": "battery.level_pct",
                        "value": 20,
                    },
                    {
                        "op": "fresh",
                        "path": "localization.pose",
                        "max_age_ms": 1000,
                    },
                ],
            }
        ]
    }
)

registry.install(machine)
```

The registry can hold multiple versions of the same capability and installs the latest version unless a version is selected explicitly.

## Mandatory requirements

A failed mandatory rule with valid evidence means `UNAVAILABLE`.

A mandatory rule depending on missing, stale, or invalid evidence means `UNKNOWN`.

Examples:

```text
battery = 10, requires >= 20
→ UNAVAILABLE

battery missing
→ UNKNOWN

battery TTL expired
→ UNKNOWN

battery = "full", numeric comparison required
→ UNKNOWN
```

## Degradation conditions

`degrade_when` describes a known operating condition where the capability remains usable but reduced.

```python
degrade_when=[
    gte("payload.utilization_pct", 90),
]
```

If payload utilization is 95% and all mandatory requirements pass, the status is `DEGRADED`.

## Primitive rules

- `equals(path, value)`
- `gte(path, threshold)`
- `gt(path, threshold)`
- `lte(path, threshold)`
- `lt(path, threshold)`
- `in_(path, values)`
- `exists(path)`
- `fresh(path, max_age_ms)`

## Composition

```python
from sense_ai import ALL, ANY, NONE_OF, NOT, ONLY_ONE
```

Composed rules retain their child outcomes.

Example:

```python
ANY(
    equals("camera.front.ready", True),
    equals("camera.rear.ready", True),
)
```

If front is `False` and rear is missing, the capability becomes `UNKNOWN` and `unknown_paths` contains:

```text
camera.rear.ready
```

It does not incorrectly point to the first rule.

## Freshness

An observation can carry source validity metadata:

```python
machine.observe(
    "battery.level_pct",
    72,
    ttl_ms=5000,
)
```

A capability can impose a stricter freshness requirement:

```python
fresh("localization.pose", max_age_ms=1000)
```

Both apply. Sense reevaluates snapshots because wall-clock time can invalidate evidence even when no new message arrives.

## Validation

Define canonical path contracts with `TelemetryFieldSpec` or `TelemetrySchema`.

```python
from sense_ai import TelemetryFieldSpec, TelemetrySchema

schema = TelemetrySchema(strict=True)
schema.define(
    TelemetryFieldSpec(
        "battery.level_pct",
        kind="number",
        minimum=0,
        maximum=100,
        ttl_ms=5000,
    )
)
```

Invalid observations are retained with `validation_errors` so the reason for `UNKNOWN` remains inspectable.

## Structured reasons

`CapabilityResult` exposes:

```text
status
blocking
warnings
unknown_paths
evaluated_at
python_warnings
```

Each `ConstraintResult` contains:

```text
code
severity
path
expected
observed
observed_age_ms
is_absent
is_stale
is_invalid
children
```

Use these fields for program logic; do not parse log strings.

## Custom Python evaluators

A clean `False` from a custom evaluator represents a concrete failure and produces `UNAVAILABLE`.

An exception means the evaluator could not determine machine state and produces `UNKNOWN`.

## Transitions

Sense emits a transition only when status changes.

```python
@machine.on_transition("warehouse.pick")
def handle(transition):
    print(transition.previous)
    print(transition.current)
    print(transition.reasons)
```

Transition reasons preserve composed-rule children.

## Privacy

```python
public = machine.snapshot().publishable_view()
```

Raw observations are excluded by default. Explicitly allow evidence only when needed.
