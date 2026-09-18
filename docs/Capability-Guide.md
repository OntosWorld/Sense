# Capability Guide

A deep dive into the capability system: how to define capabilities, write effective rules, and interpret evaluation results.

---

## defineCapability

```ts
import { defineCapability } from '@sense/sdk';

machine.defineCapability(
  defineCapability({
    name: 'my.capability',
    mandatoryRules: [...],   // required
    degradationRules: [...], // optional
  }),
);
```

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `string` | ✅ | Unique identifier. Dot-separated namespacing is conventional (e.g., `warehouse.pick`). |
| `mandatoryRules` | `Rule[]` | ✅ | All must pass → `AVAILABLE`. Any fails → `UNAVAILABLE`. |
| `degradationRules` | `Rule[]` | ❌ | Optional reduced-capability mode. All pass → fully capable. Any fail → `DEGRADED`. |

> **Degradation vs. Unavailability:** A `DEGRADED` capability is one where the machine can still perform its function, but at reduced performance or with constraints. `UNAVAILABLE` means the capability cannot be used at all until the underlying issue is resolved.

---

## Status meanings

| Status | Meaning |
|---|---|
| `AVAILABLE` | All mandatory rules pass. Degradation rules may or may not pass (see below). |
| `DEGRADED` | All mandatory rules pass, but at least one degradation rule fails. The capability works, but with reduced performance. |
| `UNAVAILABLE` | At least one mandatory rule fails. The capability cannot be used. |
| `UNKNOWN` | The machine has no observation for a path referenced by a rule. The result is indeterminate — you must supply the missing observation before a definitive status can be determined. |

### How status is determined

```
if (any mandatory rule fails)      → UNAVAILABLE
else if (any degradation rule fails) → DEGRADED
else if (any rule has no evidence)  → UNKNOWN
else                                 → AVAILABLE
```

---

## Rule types reference

All rules live in `src/rules/index.ts` and are re-exported from the SDK root.

### Value comparison

| Rule | Description |
|---|---|
| `equals(path, value)` | Observation value strictly equals `value` |
| `notEquals(path, value)` | Observation value does not equal `value` |
| `greaterThan(path, threshold)` | Numeric value > threshold |
| `greaterThanOrEqual(path, threshold)` | Numeric value ≥ threshold |
| `lessThan(path, threshold)` | Numeric value < threshold |
| `lessThanOrEqual(path, threshold)` | Numeric value ≤ threshold |

Shorthand aliases: `gt`, `gte`, `lt`, `lte`.

> **Note:** These rules use JavaScript comparison semantics. For strict type checking (e.g., comparing `"42"` vs `42`), use `equals` with the exact expected type, or preprocess observations to normalize types before ingestion.

### Existence

| Rule | Description |
|---|---|
| `exists(path)` | An observation for this path exists (value may be any type, including `null` or `false`) |
| `inSet(path, allowedValues)` | Observation value is one of the values in the array |

### Freshness

```ts
fresh(path: string, options: { maxAgeMs: number })
```

The observation must have been recorded within the last `maxAgeMs` milliseconds. If no observation exists, the rule evaluates to `UNKNOWN` (not `FAILED`).

Use freshness rules to detect stale sensor data — e.g., a lidar scan from 10 seconds ago may no longer reflect reality:

```ts
fresh('localization.pose', { maxAgeMs: 1000 }),   // must be within 1 second
fresh('safety.zone.scan', { maxAgeMs: 5000 }),   // must be within 5 seconds
```

### Logical composition

| Rule | Description |
|---|---|
| `all(...rules)` | All sub-rules pass (AND) |
| `any(...rules)` | At least one sub-rule passes (OR) |
| `not(rule)` | The sub-rule does not pass (NOT) |

Aliases: `ALL`, `ANY`, `NOT`.

```ts
import { all, any, not, equals, gte } from '@sense/sdk';

// All of: estop clear, battery above threshold, AND (gripper OR vacuum present)
all([
  equals('safety.estop', false),
  gte('battery.levelPct', 20),
  any([equals('tool.gripper.available', true), equals('tool.vacuum.available', true)]),
])

// Battery must NOT be critically low
not(lt('battery.levelPct', 5))
```

---

## The evaluation result

`machine.evaluate(capabilityName)` returns a `CapabilityEvaluationResult`:

```ts
interface CapabilityEvaluationResult {
  name: string;                    // Capability name
  status: CapabilityStatus;        // AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
  evaluatedAt: string;             // ISO 8601 timestamp of evaluation
  explanation: string;            // Human-readable summary
  failedPaths: string[];          // Paths that caused UNAVAILABLE or DEGRADED
  unknownPaths: string[];          // Paths with no observation → UNKNOWN
  unknownReason?: UnknownReasonCode;
  unavailableReason?: string;
  degradedReason?: string;
}
```

### `explanation`

A human-readable string summarising the outcome. Example:

```
All checks passed. Capable of warehouse.pick.
```

or:

```
Unavailable: battery.levelPct is 12, expected ≥ 20. Degraded: battery.levelPct is 12, expected ≥ 50.
```

Use `explanation` in logs, dashboards, and operator UIs without any parsing.

### `failedPaths`

Paths whose rules evaluated to `FAILED`. These are the **actionable** paths — fix the sensor data or hardware condition at these paths to restore the capability.

### `unknownPaths`

Paths referenced by rules that have **no observation in machine state**. Unlike `failedPaths`, these indicate missing data, not incorrect data. The recommended response is to poll the relevant sensor or mark the sensor as offline.

### Reason codes

`unavailableReason` is a human-readable string (e.g., `"battery.levelPct is 12, expected ≥ 20"`).

`unknownReason` is a structured code:

| Code | Meaning |
|---|---|
| `MISSING_OBSERVATION` | No observation exists for the referenced path |
| `STALE_OBSERVATION` | The observation exists but failed a `fresh` rule |

---

## Designing capabilities

### Naming conventions

Use dot-separated hierarchical names:

```
warehouse.pick
warehouse.place
outdoor.nav
indoor.nav
manipulator.lift
```

This makes filtering by subsystem easy and keeps transition event names human-readable.

### Granularity

Each capability should represent one **decision unit** — the smallest independently-evaluable capability that a downstream system makes a decision on. Don't combine unrelated concerns into one capability; prefer several granular capabilities that can be evaluated together:

```ts
// Prefer this:
machine.evaluate('warehouse.pick');
machine.evaluate('warehouse.place');
machine.evaluate('warehouse.nav');

// Over this:
machine.evaluate('warehouse.full-mission'); // Too coarse — hard to act on partial failures
```

### Mandatory vs. degradation rules

Ask: **"Can the machine safely perform this task even if this rule fails?"**

- If **no** → make it a `mandatoryRule`. A broken gripper absolutely prevents picking.
- If **yes, but degraded** → make it a `degradationRule`. Low battery still allows picking, just with reduced autonomy range.
- If **ambiguous** → start conservative (mandatory), relax to degradation once you've validated the degraded behavior in testing.

### Handling UNKNOWN

`UNKNOWN` status means the machine lacks the evidence to make a determination. The SDK deliberately avoids guessing. Your integration should:

1. Surface `UNKNOWN` as a **pending** or **awaiting-sensor** state in the UI.
2. Log `unknownPaths` so operators can identify which sensors are silent.
3. Use `onTransition` to detect when a previously `UNKNOWN` capability becomes `AVAILABLE` (sensor came online), which often signals the machine is now ready to accept work.

---

## Observability integration

### Transition callbacks

```ts
const unsubscribe = machine.onTransition('warehouse.pick', (t) => {
  // t.capability       — 'warehouse.pick'
  // t.previousStatus   — Status before this evaluation
  // t.currentStatus    — Status after this evaluation
  // t.timestamp        — ISO 8601
  // t.explanation      — Human-readable reason
  // t.changedPaths     — Paths whose values differ from prior evaluation
  // t.reasonCode       — Structured reason (optional)
});
```

Use callbacks to:
- Emit metrics to Prometheus / Datadog on status changes
- Publish events to peaq on `AVAILABLE → UNAVAILABLE` transitions
- Log operator-facing alerts

### Snapshot integration

Combine `getSnapshot()` with the evaluation result to build a complete audit record:

```ts
const result = machine.evaluate('warehouse.pick');
const snapshot = machine.getSnapshot(['safety.internal.status']); // redact internal paths

// Store result + snapshot for post-hoc debugging
await db.save({ capability: result.name, status: result.status, snapshot, at: new Date() });
```

See [Quickstart](./Quickstart.md) for full snapshot options including `allowPaths` and `metadata`.
