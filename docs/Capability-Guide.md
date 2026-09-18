# Capability Guide

Sense turns current machine evidence into a deterministic capability result.

## Define a capability

```python
from sense_ai import capability, equals, fresh, gte

machine.define_capability(
    capability(
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
)
```

`requires` are blocking conditions.

`degrade_when` describes conditions that indicate reduced operating quality. If one of those conditions is active while all blocking requirements pass, the capability becomes `DEGRADED`.

## Status model

| Status | Meaning |
|---|---|
| `AVAILABLE` | All required evidence exists, remains valid/fresh, and blocking constraints pass. |
| `DEGRADED` | Blocking constraints pass, but at least one degradation condition is active. |
| `UNAVAILABLE` | At least one blocking constraint fails with concrete evidence. |
| `UNKNOWN` | A required observation is missing or stale, so Sense cannot make a safe determination. |

`UNKNOWN` is deliberately distinct from `UNAVAILABLE`.

For example:

- battery = 8% and requirement is battery >= 20% → `UNAVAILABLE`
- battery reading is missing → `UNKNOWN`
- localization was valid but its evidence expired → `UNKNOWN`

## Rule primitives

Sense currently exposes:

| Rule | Meaning |
|---|---|
| `equals(path, value)` | Value must equal the expected value. |
| `gte(path, threshold)` | Numeric value must be >= threshold. |
| `gt(path, threshold)` | Numeric value must be > threshold. |
| `lte(path, threshold)` | Numeric value must be <= threshold. |
| `lt(path, threshold)` | Numeric value must be < threshold. |
| `in_(path, values)` | Value must be in the supplied set. |
| `exists(path)` | A currently valid observation must exist. |
| `fresh(path, max_age_ms)` | Observation age must not exceed the capability-specific limit. |

Logical composition:

```python
from sense_ai import ALL, ANY, NOT, NONE_OF, ONLY_ONE
```

These compose deterministic constraints without requiring a model or network service.

## Observation TTL and freshness

An observation may carry a source-level TTL:

```python
machine.observe(
    TelemetryObservation(
        path="localization.pose",
        value={"x": 1.0, "y": 2.0},
        ttl_ms=2000,
    )
)
```

Once that TTL expires, the observation is invalid for constraint evaluation.

A capability can impose a stricter limit:

```python
fresh("localization.pose", max_age_ms=500)
```

The effective behavior is conservative:

1. the observation must still be valid under its own TTL;
2. the `fresh(...)` rule must also pass.

A stale blocking observation produces `UNKNOWN`, not `AVAILABLE`.

## Structured evidence

Each failed constraint becomes a `ConstraintResult` containing fields such as:

```text
code
severity
path
expected
observed
observed_age_ms
is_absent
is_stale
```

The overall result is a `CapabilityResult`:

```python
result = machine.evaluate("warehouse.pick")

result.name
result.status
result.blocking
result.warnings
result.unknown_paths
result.evaluated_at
```

Use the structured fields for application logic. Do not parse human-readable text to make decisions.

## Reason codes

Primitive rules produce deterministic machine-readable codes such as:

```text
MISSING_LOCALIZATION_POSE
STALE_LOCALIZATION_POSE
FAIL_GTE_BATTERY_LEVEL_PCT
FAIL_EQ_SAFETY_ESTOP
```

Applications may map these codes to operator-facing language.

## Transitions

Sense records a transition whenever a capability status changes:

```python
@machine.on_transition("warehouse.pick")
def handle(transition):
    print(transition.previous)
    print(transition.current)
    print(transition.reasons)
```

A transition carries the reasons that produced the new state.

Typical transitions include:

```text
UNKNOWN → AVAILABLE
AVAILABLE → DEGRADED
DEGRADED → UNAVAILABLE
UNAVAILABLE → AVAILABLE
AVAILABLE → UNKNOWN
```

Repeated evaluation with the same status does not create another transition.

## Snapshots

```python
snapshot = machine.snapshot()
```

A snapshot reevaluates capabilities before serialization. Sense intentionally does not return a cached capability result solely because no new observation arrived: time itself can make telemetry stale.

The serialized snapshot includes:

- schema version;
- machine reference;
- optional peaq DID;
- generation timestamp;
- latest observation timestamp;
- normalized state;
- observations;
- capability status;
- blocking reasons;
- warnings;
- unknown paths.

## Privacy

Internal view:

```python
local = snapshot.local_view()
```

External view:

```python
public = snapshot.publishable_view()
```

`publishable_view()` removes raw observations by default. Allow them explicitly only when required:

```python
public = snapshot.publishable_view(
    keep_observations=["battery.*"],
)
```

## Capability design guidance

Prefer small decision-oriented capabilities:

```text
warehouse.pick
warehouse.place
navigation.indoor
navigation.outdoor
charging.accept
```

Avoid one giant capability that mixes unrelated subsystems.

A blocking rule should answer:

> If this condition fails with valid evidence, can the machine still perform the capability?

If the answer is no, put it in `requires`.

A degradation condition should represent a known reduced-quality state that still permits operation.

## UNKNOWN handling

Applications should treat `UNKNOWN` as insufficient evidence, not as success.

Common responses are:

- request or await fresh telemetry;
- keep the machine out of task selection until evidence returns;
- surface the missing/stale paths to an operator;
- publish a meaningful transition event if external systems need to know the capability became indeterminate.

## peaq integration

Sense capability state is runtime physical context. peaq remains responsible for machine identity, Activity Events, orchestration, services, markets, and economic infrastructure.

A Sense transition can be published through `PeaqContextPublisher`, while Machine Markets calls delegate to the official `PeaqosClient.orchestration` namespace.

Sense does not create an alternative marketplace schema.
