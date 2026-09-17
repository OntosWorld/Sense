# Sense SDK

**Sense** is a local-first TypeScript SDK that converts raw physical machine telemetry into structured, explainable current capability and constraint context, and allows developers to connect selected context to peaq.

## Installation

```bash
npm install @sense/sdk
```

## Quick Start

```typescript
import { SenseMachine, defineCapability, equals, gte, fresh } from '@sense/sdk';

// Create a machine instance
const machine = new SenseMachine({
  machineRef: 'robot-001',
  peaqDid: 'did:peaq:...',
});

// Define a capability with operating rules
machine.defineCapability(
  defineCapability('warehouse.pick', {
    requires: [
      equals('tool.gripper.available', true),
      equals('safety.estop', false),
      gte('battery.levelPct', 20),
      fresh('localization.pose', { maxAgeMs: 1000 }),
    ],
    degradeWhen: [gte('payload.utilizationPct', 90)],
  }),
);

// Ingest telemetry
machine.observe({
  path: 'battery.levelPct',
  value: 34,
  observedAt: new Date(),
});
machine.observe({
  path: 'tool.gripper.available',
  value: true,
  observedAt: new Date(),
});
machine.observe({
  path: 'safety.estop',
  value: false,
  observedAt: new Date(),
});

// Evaluate capability
const result = machine.evaluate('warehouse.pick');
console.log(result.status); // AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
console.log(result.reasons);

// Subscribe to state transitions
machine.onTransition('warehouse.pick', (transition) => {
  console.log(`${transition.previousStatus} → ${transition.newStatus}`);
});

// Get a structured snapshot
const snapshot = machine.snapshot();
console.log(JSON.stringify(snapshot, null, 2));
```

## Core Concepts

### Telemetry Observation

Raw machine data ingested into Sense:

```typescript
machine.observe({
  path: 'battery.levelPct',
  value: 34,
  observedAt: new Date(),
  ttlMs: 5000, // optional TTL in milliseconds
  source: 'battery-controller', // optional source identifier
});
```

### Capability Status

Every capability evaluation returns one of four statuses:

- **AVAILABLE** — All required evidence exists, is fresh, and all mandatory constraints pass.
- **DEGRADED** — Mandatory constraints permit the capability, but one or more degradation rules are active.
- **UNAVAILABLE** — At least one mandatory constraint fails.
- **UNKNOWN** — Required evidence is absent, invalid, too stale, or cannot be evaluated.

### Freshness

Freshness is a first-class feature. When evidence exceeds its permitted age, the capability becomes `UNKNOWN`:

```typescript
fresh('localization.pose', { maxAgeMs: 1000 });
```

### State Transitions

Sense detects when a capability status changes and emits structured transitions:

```typescript
machine.onTransition('warehouse.pick', (transition) => {
  // transition contains: capability, previousStatus, newStatus, timestamp, reasons
});
```

## JavaScript Usage

The SDK compiles to JavaScript and is fully usable without TypeScript:

```javascript
import { SenseMachine } from '@sense/sdk';

const machine = new SenseMachine({ machineRef: 'robot-001' });
machine.observe({ path: 'battery.levelPct', value: 34, observedAt: new Date() });
const result = machine.evaluate('warehouse.pick');
```

## Architecture

```
Telemetry Observation
        ↓
Schema Validation
        ↓
Normalized Machine State
        ↓
Freshness Engine
        ↓
Capability Rules
        ↓
Constraint Evaluation
        ↓
Context Snapshot
        ↓
Transition Engine
```

## peaq Integration

Sense binds machine context to a peaq identity and can publish selected transitions as peaq activity events. Publishing is always opt-in and raw telemetry is never uploaded automatically.

## License

Apache-2.0
