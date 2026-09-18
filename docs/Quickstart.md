# Sense SDK — Quickstart

Get from a raw telemetry stream to a publishable capability snapshot in under 10 minutes.

---

## 1. Install

```sh
npm install @sense/sdk
```

Requires Node.js ≥ 20. ESM-only.

---

## 2. Create your first machine

```ts
import { SenseMachine } from '@sense/sdk';

const machine = new SenseMachine({ machineRef: 'robot-001' });
```

`machineRef` is your developer-assigned identifier — it appears in snapshots and transition events.

---

## 3. Ingest telemetry observations

Every value flowing into Sense is an **observation**: a `(path, value, timestamp)` triple.

```ts
machine.observe({
  path: 'battery.levelPct',
  value: 78,
  observedAt: new Date(),          // Date or ISO 8601 string
});
```

You can also push multiple observations at once:

```ts
machine.observeMany([
  { path: 'safety.estop',        value: false, observedAt: new Date() },
  { path: 'tool.gripper.available', value: true,  observedAt: new Date() },
  { path: 'localization.pose',   value: { x: 1.2, y: 0.4 }, observedAt: new Date() },
]);
```

Observations are stored in memory and merged by `path`. A newer observation for the same path replaces the older one.

---

## 4. Define a capability

A **capability** is a named set of rules that evaluates to a status:

```ts
import { defineCapability, equals, gte, fresh } from '@sense/sdk';

machine.defineCapability(
  defineCapability({
    name: 'warehouse.pick',
    mandatoryRules: [
      equals('tool.gripper.available', true),
      equals('safety.estop', false),
      gte('battery.levelPct', 20),
      fresh('localization.pose', { maxAgeMs: 1000 }),
    ],
    degradationRules: [gte('battery.levelPct', 50)],
  }),
);
```

The **mandatory rules** must all pass for the capability to be `AVAILABLE`. If they fail, the capability is `UNAVAILABLE` and the SDK tells you exactly which paths caused the failure. If mandatory rules pass but **degradation rules** fail, the status is `DEGRADED` — the machine can still operate, but in a reduced capacity.

See [Capability Guide](./Capability-Guide.md) for the full rule reference and status meanings.

---

## 5. Evaluate

```ts
const result = machine.evaluate('warehouse.pick');

console.log(result.status);       // 'AVAILABLE' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN'
console.log(result.explanation);  // Human-readable string
console.log(result.failedPaths); // Paths whose rules failed (empty if AVAILABLE)
```

Evaluate once per decision point (e.g., when a task request arrives). Each evaluation also emits a **transition event** if the status changed since the last evaluation, so you can log or publish status changes:

```ts
machine.onTransition('warehouse.pick', (transition) => {
  console.log(`${transition.capability}: ${transition.previousStatus} → ${transition.currentStatus}`);
  // e.g. warehouse.pick: AVAILABLE → UNAVAILABLE
});
```

---

## 6. Build a publishable snapshot

When you need to share machine state externally (to a dashboard, peaq, or another service):

```ts
const snapshot = machine.getSnapshot();

console.log(snapshot.schemaVersion);   // '1.0'
console.log(snapshot.machineRef);       // 'robot-001'
console.log(snapshot.observations);    // Record<string, TelemetryObservation>
console.log(snapshot.timestamp);       // ISO 8601
```

Snapshots are plain JSON-compatible objects — serialize with `JSON.stringify`.

### Privacy controls

```ts
// Exclude sensitive paths from the snapshot (denylist)
const snapshot = machine.getSnapshot(['safety.internal.status']);

// Include only specific paths (allowlist) — denylist is applied on top
const snapshot = machine.getSnapshot(['safety.internal.status'], undefined, ['battery.levelPct']);

// Attach metadata (e.g., fleet ID, deployment environment)
const snapshot = machine.getSnapshot(undefined, { fleetId: 'fleet-42', env: 'production' });
```

---

## 7. Optional: publish transitions to peaq

If you have a peaq DID, configure it at construction time:

```ts
const machine = new SenseMachine({
  machineRef: 'robot-001',
  peaqDid: 'did:peaq:0x...',
});

machine.publishTransition('warehouse.pick');
```

`publishTransition` emits a peaq activity event with the snapshot attached. Set `peaqFailSilently: true` if you want failures to log and continue rather than throw.

---

## What's next?

- Read the **[Capability Guide](./Capability-Guide.md)** for the full rule reference, status explanations, and explainability fields.
- Explore **[Rules Reference](../src/rules/index.ts)** for all available rule types (`equals`, `gte`, `fresh`, `exists`, `inSet`, `all`, `any`, `not`, …).
- Check out the **Simulator Adapter** (`SimulatorAdapter`) to drive test scenarios without real hardware.
