/**
 * Sense SDK — transition engine unit tests
 * @module tests/unit/events
 */

import { describe, expect, it } from 'vitest';
import { TransitionEngine } from '../../src/events/index.js';
import type { CapabilityTransition } from '../../src/events/index.js';

describe('TransitionEngine', () => {
  it('emits a transition when capability goes from UNKNOWN to AVAILABLE', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => {
      received.push(t);
    });

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE', 'All constraints satisfied.');

    expect(received).toHaveLength(1);
    expect(received[0]!.previousStatus).toBe('UNKNOWN');
    expect(received[0]!.currentStatus).toBe('AVAILABLE');
    // Aliases also work for testing
    expect(received[0]!.from).toBe('UNKNOWN');
    expect(received[0]!.to).toBe('AVAILABLE');
  });

  it('emits a transition from AVAILABLE to DEGRADED', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => received.push(t));

    engine.recordTransition('warehouse.pick', 'AVAILABLE', 'DEGRADED');

    expect(received).toHaveLength(1);
    expect(received[0]!.currentStatus).toBe('DEGRADED');
  });

  it('emits a transition from DEGRADED to UNAVAILABLE', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => received.push(t));

    engine.recordTransition('warehouse.pick', 'DEGRADED', 'UNAVAILABLE');

    expect(received).toHaveLength(1);
    expect(received[0]!.currentStatus).toBe('UNAVAILABLE');
  });

  it('emits a transition from UNAVAILABLE to AVAILABLE', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => received.push(t));

    engine.recordTransition('warehouse.pick', 'UNAVAILABLE', 'AVAILABLE');

    expect(received).toHaveLength(1);
    expect(received[0]!.previousStatus).toBe('UNAVAILABLE');
    expect(received[0]!.currentStatus).toBe('AVAILABLE');
  });

  it('does NOT emit when from equals to', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => received.push(t));

    engine.recordTransition('warehouse.pick', 'AVAILABLE', 'AVAILABLE');

    expect(received).toHaveLength(0);
  });

  it('does NOT emit when from is UNKNOWN and to is UNKNOWN', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => received.push(t));

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'UNKNOWN');

    expect(received).toHaveLength(0);
  });

  it('allows multiple subscribers for the same capability', () => {
    const engine = new TransitionEngine();
    const first: CapabilityTransition[] = [];
    const second: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => first.push(t));
    engine.onTransition('warehouse.pick', (t) => second.push(t));

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(first).toHaveLength(1);
    expect(second).toHaveLength(1);
  });

  it('subscribers fire in registration order', () => {
    const engine = new TransitionEngine();
    const order: number[] = [];

    engine.onTransition('warehouse.pick', () => order.push(1));
    engine.onTransition('warehouse.pick', () => order.push(2));
    engine.onTransition('warehouse.pick', () => order.push(3));

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(order).toEqual([1, 2, 3]);
  });

  it('can unsubscribe via returned function', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    const unsub = engine.onTransition('warehouse.pick', (t) => received.push(t));
    unsub();

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(received).toHaveLength(0);
  });

  it('multiple unsubscribe calls are safe', () => {
    const engine = new TransitionEngine();
    const received: CapabilityTransition[] = [];

    const unsub = engine.onTransition('warehouse.pick', (t) => received.push(t));
    unsub();
    unsub(); // second call should be no-op

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(received).toHaveLength(0);
  });

  it('handles multiple capabilities independently', () => {
    const engine = new TransitionEngine();
    const pick: CapabilityTransition[] = [];
    const move: CapabilityTransition[] = [];

    engine.onTransition('warehouse.pick', (t) => pick.push(t));
    engine.onTransition('warehouse.move', (t) => move.push(t));

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');
    engine.recordTransition('warehouse.move', 'UNAVAILABLE', 'DEGRADED');

    expect(pick).toHaveLength(1);
    expect(move).toHaveLength(1);
  });

  it('transitions include the capability name', () => {
    const engine = new TransitionEngine();
    let captured!: CapabilityTransition;

    engine.onTransition('warehouse.pick', (t) => {
      captured = t;
    });

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(captured.capability).toBe('warehouse.pick');
  });

  it('transitions include an explanation', () => {
    const engine = new TransitionEngine();
    let captured!: CapabilityTransition;

    engine.onTransition('warehouse.pick', (t) => {
      captured = t;
    });

    engine.recordTransition('warehouse.pick', 'AVAILABLE', 'UNAVAILABLE', 'ESTOP activated');

    expect(captured.explanation).toBe('ESTOP activated');
  });

  it('transitions include a timestamp', () => {
    const engine = new TransitionEngine();
    let captured!: CapabilityTransition;

    engine.onTransition('warehouse.pick', (t) => {
      captured = t;
    });

    const before = Date.now();
    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');
    const after = Date.now();

    const ts = Date.parse(captured.timestamp);
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });

  it('callback receives a frozen copy of the transition', () => {
    const engine = new TransitionEngine();
    let receivedFrozen = false;

    engine.onTransition('warehouse.pick', (t) => {
      receivedFrozen = Object.isFrozen(t);
    });

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(receivedFrozen).toBe(true);
  });

  it('callback cannot mutate the transition', () => {
    const engine = new TransitionEngine();
    let received!: CapabilityTransition;

    engine.onTransition('warehouse.pick', (t) => {
      received = t;
    });

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(() => {
      // @ts-expect-error — intentionally trying to mutate frozen object
      received.currentStatus = 'DEGRADED';
    }).toThrow();
  });

  it('includes changedPaths (empty when recorded directly)', () => {
    const engine = new TransitionEngine();
    let captured!: CapabilityTransition;

    engine.onTransition('warehouse.pick', (t) => {
      captured = t;
    });

    engine.recordTransition('warehouse.pick', 'UNKNOWN', 'AVAILABLE');

    expect(Array.isArray(captured.changedPaths)).toBe(true);
  });

  it('uses default explanation when not provided', () => {
    const engine = new TransitionEngine();
    let captured!: CapabilityTransition;

    engine.onTransition('warehouse.pick', (t) => {
      captured = t;
    });

    engine.recordTransition('warehouse.pick', 'AVAILABLE', 'DEGRADED');

    expect(captured.explanation).toBe('warehouse.pick changed');
  });
});
