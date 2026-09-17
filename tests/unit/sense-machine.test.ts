/**
 * Sense SDK — SenseMachine unit tests
 * @module tests/unit/sense-machine
 */

import { describe, expect, it } from 'vitest';
import { SenseMachine } from '../../src/sense-machine.js';
import { defineCapability, equals, gte, lessThan, fresh } from '../../src/index.js';
import type { CapabilityTransition } from '../../src/events/index.js';

function recentIso(ageMs: number): string {
  return new Date(Date.now() - ageMs).toISOString();
}

describe('SenseMachine', () => {
  describe('constructor', () => {
    it('accepts machineRef only', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      expect(machine.machineRef).toBe('robot-001');
    });

    it('accepts machineRef and peaqDid', () => {
      const machine = new SenseMachine({
        machineRef: 'robot-001',
        peaqDid: 'did:peaq:0x123',
      });
      expect(machine.machineRef).toBe('robot-001');
      expect(machine.peaqDid).toBe('did:peaq:0x123');
    });
  });

  describe('observe()', () => {
    it('accepts a TelemetryObservation', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({
        path: 'battery.levelPct',
        value: 85,
        observedAt: recentIso(0),
      });

      const state = machine.getState();
      expect(state.observations.get('battery.levelPct')?.value).toBe(85);
    });

    it('accepts path, value, observedAt shorthand', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({ path: 'battery.levelPct', value: 85, observedAt: recentIso(0) });

      const state = machine.getState();
      expect(state.observations.get('battery.levelPct')?.value).toBe(85);
    });

    it('accepts ttlMs', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({
        path: 'battery.levelPct',
        value: 85,
        observedAt: recentIso(0),
        ttlMs: 10_000,
      });

      const state = machine.getState();
      expect(state.observations.get('battery.levelPct')?.ttlMs).toBe(10_000);
    });

    it('accepts source', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({
        path: 'safety.estop',
        value: false,
        observedAt: recentIso(0),
        source: 'safety-controller',
      });

      const state = machine.getState();
      expect(state.observations.get('safety.estop')?.source).toBe('safety-controller');
    });

    it('updates existing observation', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({ path: 'battery.levelPct', value: 85, observedAt: recentIso(0) });
      machine.observe({ path: 'battery.levelPct', value: 72, observedAt: recentIso(0) });

      const state = machine.getState();
      expect(state.observations.get('battery.levelPct')?.value).toBe(72);
    });

    it('returns this for chaining', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      const result = machine.observe({
        path: 'battery.levelPct',
        value: 85,
        observedAt: recentIso(0),
      });
      expect(result).toBe(machine);
    });
  });

  describe('defineCapability()', () => {
    it('registers a capability', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      const cap = defineCapability('warehouse.pick', {
        requires: [equals('safety.estop', false)],
      });

      machine.defineCapability(cap);
      const result = machine.evaluate('warehouse.pick');

      expect(result?.status).toBe('UNKNOWN'); // no evidence yet
    });

    it('throws on duplicate capability name', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      const cap = defineCapability('warehouse.pick', {
        requires: [equals('safety.estop', false)],
      });

      machine.defineCapability(cap);
      expect(() => machine.defineCapability(cap)).toThrow();
    });
  });

  describe('evaluate()', () => {
    it('returns AVAILABLE when all mandatory constraints pass', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [
            equals('safety.estop', false),
            gte('battery.levelPct', 20),
            equals('tool.gripper.available', true),
          ],
        }),
      );

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.observe({ path: 'battery.levelPct', value: 80, observedAt: recentIso(0) });
      machine.observe({ path: 'tool.gripper.available', value: true, observedAt: recentIso(0) });

      const result = machine.evaluate('warehouse.pick');
      expect(result?.status).toBe('AVAILABLE');
    });

    it('returns UNAVAILABLE when a mandatory constraint fails', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false), gte('battery.levelPct', 20)],
        }),
      );

      machine.observe({ path: 'safety.estop', value: true, observedAt: recentIso(0) }); // estop active
      machine.observe({ path: 'battery.levelPct', value: 80, observedAt: recentIso(0) });

      const result = machine.evaluate('warehouse.pick');
      expect(result?.status).toBe('UNAVAILABLE');
      expect(result?.explanation).toContain('safety.estop');
    });

    it('returns DEGRADED when mandatory pass but degradation rule fails', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false)],
          degrade: [gte('battery.levelPct', 50)], // fails when battery < 50 → DEGRADED
        }),
      );

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.observe({ path: 'battery.levelPct', value: 35, observedAt: recentIso(0) });

      const result = machine.evaluate('warehouse.pick');
      expect(result?.status).toBe('DEGRADED');
    });

    it('returns UNKNOWN when required evidence is missing', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('battery.levelPct', 80)],
        }),
      );

      // Do not observe battery.levelPct
      const result = machine.evaluate('warehouse.pick');
      expect(result?.status).toBe('UNKNOWN');
      expect(result?.unknownReason).toBeTruthy();
    });

    it('returns UNKNOWN when required fresh evidence is stale', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false), fresh('localization.pose', { maxAgeMs: 1000 })],
        }),
      );

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      // localization.pose is 5 seconds old — exceeds maxAgeMs of 1000ms
      machine.observe({
        path: 'localization.pose',
        value: { x: 1, y: 2 },
        observedAt: recentIso(5000),
      });

      const result = machine.evaluate('warehouse.pick');
      expect(result?.status).toBe('UNKNOWN');
      expect(result?.unknownReason).toBe('STALE_EVIDENCE');
    });

    it('returns undefined for an unregistered capability', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      const result = machine.evaluate('unknown.capability');
      expect(result).toBeUndefined();
    });

    it('includes all mandatory rule results', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false), gte('battery.levelPct', 20)],
        }),
      );

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.observe({ path: 'battery.levelPct', value: 80, observedAt: recentIso(0) });

      const result = machine.evaluate('warehouse.pick');
      expect(result?.mandatoryRuleResults).toHaveLength(2);
    });
  });

  describe('onTransition()', () => {
    it('fires callback on capability state change', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false)],
        }),
      );

      const received: CapabilityTransition[] = [];
      machine.onTransition('warehouse.pick', (t) => received.push(t));

      // Unknown → Available
      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.evaluate('warehouse.pick');

      expect(received).toHaveLength(1);
      expect(received[0]!.currentStatus).toBe('AVAILABLE');
    });

    it('does not fire on repeated evaluation with same result', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false)],
        }),
      );

      const received: CapabilityTransition[] = [];
      machine.onTransition('warehouse.pick', (t) => received.push(t));

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.evaluate('warehouse.pick');
      machine.evaluate('warehouse.pick'); // same state
      machine.evaluate('warehouse.pick'); // same state again

      expect(received).toHaveLength(1);
    });

    it('fires again on state change after returning to same state', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false)],
        }),
      );

      const received: CapabilityTransition[] = [];
      machine.onTransition('warehouse.pick', (t) => received.push(t));

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.evaluate('warehouse.pick'); // UNKNOWN → AVAILABLE

      machine.observe({ path: 'safety.estop', value: true, observedAt: recentIso(0) });
      machine.evaluate('warehouse.pick'); // AVAILABLE → UNAVAILABLE

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.evaluate('warehouse.pick'); // UNAVAILABLE → AVAILABLE

      expect(received).toHaveLength(3);
    });

    it('returns an unsubscribe function', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.defineCapability(
        defineCapability('warehouse.pick', {
          requires: [equals('safety.estop', false)],
        }),
      );

      const received: CapabilityTransition[] = [];
      const unsub = machine.onTransition('warehouse.pick', (t) => received.push(t));
      unsub();

      machine.observe({ path: 'safety.estop', value: false, observedAt: recentIso(0) });
      machine.evaluate('warehouse.pick');

      expect(received).toHaveLength(0);
    });
  });

  describe('getSnapshot()', () => {
    it('returns a ContextSnapshot', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({ path: 'battery.levelPct', value: 80, observedAt: recentIso(0) });

      const snapshot = machine.getSnapshot();
      expect(snapshot.schemaVersion).toBe('1.0');
      expect(snapshot.machineRef).toBe('robot-001');
      expect(typeof snapshot.observations).toBe('object');
    });

    it('includes peaqDid when set', () => {
      const machine = new SenseMachine({
        machineRef: 'robot-001',
        peaqDid: 'did:peaq:0xabc',
      });
      machine.observe({ path: 'battery.levelPct', value: 80, observedAt: recentIso(0) });

      const snapshot = machine.getSnapshot();
      expect(snapshot.peaqDid).toBe('did:peaq:0xabc');
    });

    it('serializes to JSON', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({ path: 'battery.levelPct', value: 80, observedAt: recentIso(0) });

      const json = JSON.stringify(machine.getSnapshot());
      const parsed = JSON.parse(json);

      expect(parsed.schemaVersion).toBe('1.0');
      expect(parsed.observations['battery.levelPct'].value).toBe(80);
    });
  });

  describe('getState()', () => {
    it('returns the current NormalizedMachineState', () => {
      const machine = new SenseMachine({ machineRef: 'robot-001' });
      machine.observe({ path: 'battery.levelPct', value: 80, observedAt: recentIso(0) });

      const state = machine.getState();
      expect(state.observations.get('battery.levelPct')?.value).toBe(80);
    });
  });
});
