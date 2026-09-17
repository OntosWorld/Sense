/**
 * Sense SDK — MVP Demo: warehouse.pick capability
 *
 * Demonstrates the complete vertical slice:
 *   Raw telemetry → Sense → Normalized state → Capability evaluation → Transitions
 *
 * Run: npm install && npm run run
 * (from the examples/warehouse-pick directory)
 *
 * Or from the repo root with tsx:
 *   npx tsx examples/warehouse-pick/index.ts
 */

import { SenseMachine, defineCapability, equals, gte, lessThan, fresh } from '../../src/index.js';

// ---------------------------------------------------------------------------
// Capability definition
// ---------------------------------------------------------------------------

const warehousePick = defineCapability('warehouse.pick', {
  description: 'Robot can perform a warehouse pick operation.',
  requires: [
    // Safety
    equals('safety.estop', false),
    // Power
    gte('battery.levelPct', 20),
    // Localization must be recent
    fresh('localization.pose', { maxAgeMs: 2000 }),
    // Tool must be available
    equals('tool.gripper.available', true),
    // Payload within limits
    lessThan('payload.currentKg', 20),
  ],
  degrade: [
    // Degrade if battery is low (but still usable)
    lessThan('battery.levelPct', 50),
  ],
});

// ---------------------------------------------------------------------------
// Simulated telemetry feed
// ---------------------------------------------------------------------------

const machine = new SenseMachine({
  machineRef: 'warehouse-robot-001',
  // In production, associate with a peaq machine DID:
  // peaqDid: 'did:peaq:0x...',
});

machine.defineCapability(warehousePick);

// Subscribe to all transitions
machine.onTransition('warehouse.pick', (transition) => {
  console.log(`\n🔔 TRANSITION: warehouse.pick  ${transition.from} → ${transition.to}`);
  console.log(`   reason: ${transition.reason}`);
  console.log(`   at: ${transition.timestamp}`);
});

function observe(key: string, value: unknown, ageMs = 0): void {
  machine.observe({
    path: key,
    value,
    observedAt: new Date(Date.now() - ageMs),
    ttlMs: 10_000,
    source: 'simulator',
  });
}

function evaluate(): void {
  const result = machine.evaluate('warehouse.pick');
  if (!result) return;

  const statusIcon =
    result.status === 'AVAILABLE'
      ? '🟢'
      : result.status === 'DEGRADED'
        ? '🟡'
        : result.status === 'UNAVAILABLE'
          ? '🔴'
          : '⚪';

  console.log(`\n  ${statusIcon} warehouse.pick: ${result.status}`);
  console.log(`     ${result.explanation}`);

  if (result.status === 'DEGRADED') {
    console.log(
      `     degradation rules:`,
      result.degradationRuleResults
        .filter((r) => !r.passed)
        .map((r) => r.reason)
        .join(', '),
    );
  }

  if (result.status === 'UNKNOWN' && result.unknownReason) {
    console.log(`     unknown reason: ${result.unknownReason}`);
  }
}

// ---------------------------------------------------------------------------
// Scenario 1: All constraints satisfied → AVAILABLE
// ---------------------------------------------------------------------------

console.log('\n════════════════════════════════════════');
console.log('  SCENARIO 1 — All constraints satisfied');
console.log('════════════════════════════════════════');

observe('safety.estop', false);
observe('battery.levelPct', 78);
observe('localization.pose', { x: 1.2, y: 3.4, theta: 0.05 });
observe('tool.gripper.available', true);
observe('payload.currentKg', 8);

evaluate();

// ---------------------------------------------------------------------------
// Scenario 2: Localization goes stale → UNKNOWN (STALE_EVIDENCE)
// ---------------------------------------------------------------------------

console.log('\n════════════════════════════════════════');
console.log('  SCENARIO 2 — Localization data is stale');
console.log('════════════════════════════════════════');

// Advance time — localization.pose is now 5 seconds old (maxAgeMs = 2000)
observe('localization.pose', { x: 1.2, y: 3.4, theta: 0.05 }, 5_000);

evaluate();

// ---------------------------------------------------------------------------
// Scenario 3: Localization restored, payload over limit → UNAVAILABLE
// ---------------------------------------------------------------------------

console.log('\n════════════════════════════════════════');
console.log('  SCENARIO 3 — Payload exceeds configured maximum');
console.log('════════════════════════════════════════');

observe('localization.pose', { x: 1.5, y: 3.6, theta: 0.1 }); // fresh again
observe('payload.currentKg', 21); // exceeds 20 kg limit

evaluate();

// ---------------------------------------------------------------------------
// Scenario 4: Payload back in range, battery low → DEGRADED
// ---------------------------------------------------------------------------

console.log('\n════════════════════════════════════════');
console.log('  SCENARIO 4 — Mandatory OK, battery low → DEGRADED');
console.log('════════════════════════════════════════');

observe('payload.currentKg', 8); // back in range
observe('battery.levelPct', 35); // below 50% degradation threshold

evaluate();

// ---------------------------------------------------------------------------
// Final: Serialized context snapshot
// ---------------------------------------------------------------------------

console.log('\n════════════════════════════════════════');
console.log('  CONTEXT SNAPSHOT (JSON)');
console.log('════════════════════════════════════════');

const snapshot = machine.getSnapshot();
console.log(JSON.stringify(snapshot, null, 2));

console.log('\n✅ MVP demo complete.\n');
