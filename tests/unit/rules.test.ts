/**
 * Unit tests — rules
 */
import { describe, it, expect } from 'vitest';
import { emptyState, applyObservation } from '../../src/model/state.js';
import {
  equals,
  notEquals,
  greaterThan,
  greaterThanOrEqual,
  lessThan,
  lessThanOrEqual,
  exists,
  inSet,
  fresh,
  all,
  any,
  not,
  evaluateRule,
  deepEqual,
  type Rule,
} from '../../src/rules/index.js';
import { MissingEvidenceError, InvalidRuleError } from '../../src/errors/index.js';

function makeState(observations: Record<string, unknown>): ReturnType<typeof emptyState> {
  let state = emptyState();
  const now = new Date();
  for (const [path, value] of Object.entries(observations)) {
    state = applyObservation(state, {
      path,
      value,
      observedAt: now.toISOString(),
    });
  }
  return state;
}

const NOW_MS = Date.parse('2024-01-01T12:00:00.000Z');
const NOW_DATE = new Date(NOW_MS).toISOString();

function makeStaleState(observations: Record<string, unknown>, ageMs: number) {
  let state = emptyState();
  const observedAt = new Date(NOW_MS - ageMs).toISOString();
  for (const [path, value] of Object.entries(observations)) {
    state = applyObservation(state, { path, value, observedAt, ttlMs: ageMs - 1 });
  }
  return state;
}

describe('equals rule', () => {
  it('passes when value matches', () => {
    const state = makeState({ 'safety.estop': false });
    const result = evaluateRule(equals('safety.estop', false), state, NOW_MS);
    expect(result.passed).toBe(true);
  });

  it('fails when value does not match', () => {
    const state = makeState({ 'safety.estop': false });
    const result = evaluateRule(equals('safety.estop', true), state, NOW_MS);
    expect(result.passed).toBe(false);
  });

  it('fails when path is missing', () => {
    const state = makeState({});
    const result = evaluateRule(equals('safety.estop', false), state, NOW_MS);
    expect(result.passed).toBe(false);
  });
});

describe('notEquals rule', () => {
  it('passes when value does not match', () => {
    const state = makeState({ 'safety.estop': false });
    const result = evaluateRule(notEquals('safety.estop', true), state, NOW_MS);
    expect(result.passed).toBe(true);
  });

  it('fails when value matches', () => {
    const state = makeState({ 'safety.estop': false });
    const result = evaluateRule(notEquals('safety.estop', false), state, NOW_MS);
    expect(result.passed).toBe(false);
  });
});

describe('greaterThan rule', () => {
  it('passes when value is greater', () => {
    const state = makeState({ 'battery.levelPct': 50 });
    const result = evaluateRule(greaterThan('battery.levelPct', 20), state, NOW_MS);
    expect(result.passed).toBe(true);
  });

  it('fails when value is equal', () => {
    const state = makeState({ 'battery.levelPct': 20 });
    const result = evaluateRule(greaterThan('battery.levelPct', 20), state, NOW_MS);
    expect(result.passed).toBe(false);
  });

  it('fails when value is less', () => {
    const state = makeState({ 'battery.levelPct': 10 });
    const result = evaluateRule(greaterThan('battery.levelPct', 20), state, NOW_MS);
    expect(result.passed).toBe(false);
  });

  it('throws when value is non-numeric', () => {
    const state = makeState({ 'battery.levelPct': 'high' });
    expect(() => evaluateRule(greaterThan('battery.levelPct', 20), state, NOW_MS)).toThrow(
      InvalidRuleError,
    );
  });
});

describe('greaterThanOrEqual rule', () => {
  it('passes when value is greater', () => {
    const state = makeState({ 'battery.levelPct': 50 });
    expect(evaluateRule(greaterThanOrEqual('battery.levelPct', 20), state, NOW_MS).passed).toBe(
      true,
    );
  });

  it('passes when value is equal', () => {
    const state = makeState({ 'battery.levelPct': 20 });
    expect(evaluateRule(greaterThanOrEqual('battery.levelPct', 20), state, NOW_MS).passed).toBe(
      true,
    );
  });

  it('fails when value is less', () => {
    const state = makeState({ 'battery.levelPct': 10 });
    expect(evaluateRule(greaterThanOrEqual('battery.levelPct', 20), state, NOW_MS).passed).toBe(
      false,
    );
  });
});

describe('lessThan rule', () => {
  it('passes when value is less', () => {
    const state = makeState({ 'battery.levelPct': 10 });
    expect(evaluateRule(lessThan('battery.levelPct', 20), state, NOW_MS).passed).toBe(true);
  });

  it('fails when value is equal', () => {
    const state = makeState({ 'battery.levelPct': 20 });
    expect(evaluateRule(lessThan('battery.levelPct', 20), state, NOW_MS).passed).toBe(false);
  });
});

describe('lessThanOrEqual rule', () => {
  it('passes when value is less or equal', () => {
    const state = makeState({ 'battery.levelPct': 20 });
    expect(evaluateRule(lessThanOrEqual('battery.levelPct', 20), state, NOW_MS).passed).toBe(true);
  });
});

describe('exists rule', () => {
  it('passes when path exists', () => {
    const state = makeState({ 'gripper.available': true });
    expect(evaluateRule(exists('gripper.available'), state, NOW_MS).passed).toBe(true);
  });

  it('fails when path is missing', () => {
    const state = makeState({});
    expect(evaluateRule(exists('gripper.available'), state, NOW_MS).passed).toBe(false);
  });
});

describe('inSet rule', () => {
  it('passes when value is in the set', () => {
    const state = makeState({ 'localization.status': 'valid' });
    const result = evaluateRule(
      inSet('localization.status', ['valid', 'calibrating']),
      state,
      NOW_MS,
    );
    expect(result.passed).toBe(true);
  });

  it('fails when value is not in the set', () => {
    const state = makeState({ 'localization.status': 'lost' });
    const result = evaluateRule(
      inSet('localization.status', ['valid', 'calibrating']),
      state,
      NOW_MS,
    );
    expect(result.passed).toBe(false);
  });
});

describe('fresh rule', () => {
  it('passes when observation is within maxAgeMs', () => {
    const state = makeState({ 'localization.pose': { x: 1, y: 2 } });
    const result = evaluateRule(fresh('localization.pose', { maxAgeMs: 5_000 }), state, NOW_MS);
    expect(result.passed).toBe(true);
  });

  it('fails when observation is missing', () => {
    const state = makeState({});
    const result = evaluateRule(fresh('localization.pose', { maxAgeMs: 5_000 }), state, NOW_MS);
    expect(result.passed).toBe(false);
  });

  it('throws when maxAgeMs is negative', () => {
    expect(() => fresh('localization.pose', { maxAgeMs: -1 })).toThrow(InvalidRuleError);
  });

  it('throws when maxAgeMs is not a number', () => {
    expect(() => fresh('localization.pose', { maxAgeMs: 'fast' as unknown as number })).toThrow(
      InvalidRuleError,
    );
  });
});

describe('all (AND) rule', () => {
  it('passes when all rules pass', () => {
    const state = makeState({ a: 10, b: 20 });
    const result = evaluateRule(all([greaterThan('a', 5), greaterThan('b', 10)]), state, NOW_MS);
    expect(result.passed).toBe(true);
  });

  it('fails when one rule fails', () => {
    const state = makeState({ a: 10, b: 5 });
    const result = evaluateRule(all([greaterThan('a', 5), greaterThan('b', 10)]), state, NOW_MS);
    expect(result.passed).toBe(false);
  });

  it('throws with fewer than 2 rules', () => {
    expect(() => all([greaterThan('a', 5)])).toThrow(InvalidRuleError);
  });
});

describe('any (OR) rule', () => {
  it('passes when at least one rule passes', () => {
    const state = makeState({ a: 3, b: 20 });
    const result = evaluateRule(any([greaterThan('a', 5), greaterThan('b', 10)]), state, NOW_MS);
    expect(result.passed).toBe(true);
  });

  it('fails when all rules fail', () => {
    const state = makeState({ a: 3, b: 5 });
    const result = evaluateRule(any([greaterThan('a', 5), greaterThan('b', 10)]), state, NOW_MS);
    expect(result.passed).toBe(false);
  });
});

describe('not rule', () => {
  it('passes when the inner rule fails', () => {
    const state = makeState({ a: 3 });
    const result = evaluateRule(not(greaterThan('a', 5)), state, NOW_MS);
    expect(result.passed).toBe(true);
  });

  it('fails when the inner rule passes', () => {
    const state = makeState({ a: 10 });
    const result = evaluateRule(not(greaterThan('a', 5)), state, NOW_MS);
    expect(result.passed).toBe(false);
  });
});

describe('deepEqual', () => {
  it('compares primitives correctly', () => {
    expect(deepEqual(42, 42)).toBe(true);
    expect(deepEqual(42, '42')).toBe(false);
    expect(deepEqual(null, undefined)).toBe(false);
  });

  it('compares arrays correctly', () => {
    expect(deepEqual([1, 2, 3], [1, 2, 3])).toBe(true);
    expect(deepEqual([1, 2], [1, 2, 3])).toBe(false);
  });

  it('compares objects correctly', () => {
    expect(deepEqual({ a: 1, b: 2 }, { a: 1, b: 2 })).toBe(true);
    expect(deepEqual({ a: 1 }, { a: 1, b: 2 })).toBe(false);
  });

  it('compares nested structures correctly', () => {
    expect(deepEqual({ a: [1, { b: 2 }] }, { a: [1, { b: 2 }] })).toBe(true);
    expect(deepEqual({ a: [1, { b: 2 }] }, { a: [1, { b: 3 }] })).toBe(false);
  });
});
