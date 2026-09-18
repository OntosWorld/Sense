# Capability Guide

Sense capabilities describe what a physical machine can **currently** do from the evidence available to the SDK.

## Define a capability

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

### `requires`

Mandatory conditions. If a known value fails one, the result is `UNAVAILABLE`.

If required evidence is absent or stale, the result is `UNKNOWN`.

### `degrade_when`

Conditions that describe a degraded state. When one is active and all mandatory requirements still pass, the result is `DEGRADED`.

## Status model

| Status | Meaning |
|---|---|
| `AVAILABLE` | Required evidence exists and mandatory rules pass. |
| `DEGRADED` | Mandatory rules pass but a degradation condition is active. |
| `UNAVAILABLE` | A mandatory rule has a concrete failing value. |
| `UNKNOWN` | Required evidence is missing or stale. |

`UNKNOWN` is deliberately separate from `UNAVAILABLE`.

## Rule primitives

```python
from sense_ai import (
    ALL,
    ANY,
    NONE_OF,
    NOT,
    ONLY_ONE,
    equals,
    exists,
    fresh,
    gt,
    gte,
    in_,
    lt,
    lte,
)
```

Common examples:

```python
equals("safety.estop", False)
gte("battery.level_pct", 20)
lt("motor.temperature_c", 80)
in_("operation.mode", ["auto", "assisted"])
exists("tool.gripper.available")
fresh("localization.pose", max_age_ms=1000)
```

Logical composition:

```python
ALL(rule_a, rule_b)
ANY(rule_a, rule_b)
NOT(rule_a)
NONE_OF(rule_a, rule_b)
ONLY_ONE(rule_a, rule_b)
```

## Freshness

Freshness is evaluated from the source observation time.

```python
machine.observe(
    "localization.pose",
    {"x": 1.0, "y": 2.0},
    observed_at=source_timestamp,
    received_at=receipt_timestamp,
    ttl_ms=1500,
)
```

- `observed_at`: when the source measured the value.
- `received_at`: when Sense received it.
- `ttl_ms`: source-declared validity metadata.
- `fresh(...)`: capability-specific maximum evidence age.

Snapshots are re-evaluated every time, because evidence can become stale without a new message arriving.

## Evaluation result

```python
result = machine.evaluate("warehouse.pick")

print(result.status)
print(result.unknown_paths)

for reason in result.reasons:
    print(reason.code)
    print(reason.severity)
    print(reason.path)
    print(reason.expected)
    print(reason.observed)
    print(reason.observed_age_ms)
```

Reasons are structured so applications can react without parsing human text.

## Structured telemetry

Observation values are JSON-compatible and can be nested:

```python
machine.observe(
    "localization.pose",
    {
        "position": {"x": 1.0, "y": 2.0, "z": 0.0},
        "quality": {"covariance": [0.01, 0.02]},
    },
)
```

Rules operate on explicit observation paths. Do not bury values that need independent rules inside an opaque object unless the application deliberately treats that object as one piece of evidence.

## Read current observations

Preferred:

```python
observation = machine.get_observation("battery.level_pct")
```

The older `machine.observe("battery.level_pct")` read form remains for compatibility.

## Transitions

```python
@machine.on_transition("warehouse.pick")
def changed(transition):
    print(transition.previous)
    print(transition.current)
    print(transition.reasons)
```

Sense emits a transition only when the capability status changes.

This is the preferred unit for external event systems such as peaq. Do not publish every raw sensor update unless the application genuinely needs that behavior.

## Snapshots

```python
snapshot = machine.snapshot()
payload = snapshot.to_dict()
json_text = snapshot.to_json(indent=2)
```

The canonical language-neutral contract lives at:

```text
schemas/context-1.0.schema.json
```

Schema versioning is independent from the Python package version.

## Data minimization

Keep only selected local fields:

```python
subset = snapshot.redact(
    keep_observations=["battery.*", "localization.*"],
)
```

External publication defaults to no raw observations:

```python
public = snapshot.publishable_view()
assert public.observations == {}
```

Explicitly allow raw evidence when needed:

```python
public = snapshot.publishable_view(
    keep_observations=["battery.level_pct"],
)
```

## Capability design guidance

Prefer capabilities that describe meaningful machine work:

```text
warehouse.pick
navigation.ready
inspection.capture
delivery.ready
charging.accept
```

Avoid vague capabilities such as:

```text
healthy
good
trusted
smart
```

A useful capability should make it clear what action is being evaluated and which physical evidence controls the answer.

## Safety boundary

Sense is an information and evaluation layer. A result such as `AVAILABLE` is **not** a functional-safety certification and must not directly bypass a machine's safety controller, interlocks, emergency-stop system, or OEM safety logic.
