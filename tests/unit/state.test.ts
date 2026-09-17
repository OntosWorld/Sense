/**
 * Sense SDK — state unit tests
 * @module tests/unit/state
 */

import { describe, expect, it } from 'vitest';
import { emptyState, applyObservation, getObservation } from '../../src/model/state.js';
import type { TelemetryObservation } from '../../src/model/observation.js';

function makeObs(
  path: string,
  value: unknown,
  ageMs = 0,
  overrides: Partial<TelemetryObservation> = {},
): TelemetryObservation {
  const observedAt = new Date(Date.now() - ageMs).toISOString();
  return {
    path,
    value,
    observedAt,
    source: 'test',
    ...overrides,
  };
}

describe('emptyState', () => {
  it('creates an empty state with no observations', () => {
    const state = emptyState();
    expect(state.observations.size).toBe(0);
    expect(state.updatedAt).toBeTruthy();
    expect(typeof state.updatedAt).toBe('string');
  });
});

describe('applyObservation', () => {
  it('adds a new observation', () => {
    const state = emptyState();
    const obs = makeObs('battery.levelPct', 85);
    const next = applyObservation(state, obs);

    expect(getObservation(next, 'battery.levelPct')).toMatchObject({
      path: 'battery.levelPct',
      value: 85,
    });
  });

  it('updates an existing observation', () => {
    const obs1 = makeObs('battery.levelPct', 85, 10_000);
    const obs2 = makeObs('battery.levelPct', 72, 0);

    const s1 = applyObservation(emptyState(), obs1);
    const s2 = applyObservation(s1, obs2);

    expect(getObservation(s2, 'battery.levelPct')?.value).toBe(72);
  });

  it('tracks multiple independent paths', () => {
    const state = emptyState();
    const s1 = applyObservation(state, makeObs('battery.levelPct', 90));
    const s2 = applyObservation(s1, makeObs('safety.estop', false));
    const s3 = applyObservation(s2, makeObs('tool.gripper.available', true));

    expect(s3.observations.size).toBe(3);
    expect(getObservation(s3, 'battery.levelPct')?.value).toBe(90);
    expect(getObservation(s3, 'safety.estop')?.value).toBe(false);
    expect(getObservation(s3, 'tool.gripper.available')?.value).toBe(true);
  });

  it('updates updatedAt timestamp', () => {
    const before = Date.now();
    const obs = makeObs('battery.levelPct', 80, 0);
    const state = applyObservation(emptyState(), obs);
    const after = Date.now();

    expect(state.updatedAt).toBeTruthy();
    const ts = Date.parse(state.updatedAt);
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });

  it('preserves old observation when new one is older', () => {
    // New observation arrives but is older (e.g., out-of-order network delivery)
    const obs1 = makeObs('battery.levelPct', 85, 0);
    const obs2 = makeObs('battery.levelPct', 80, 1000); // 1s older

    const s1 = applyObservation(emptyState(), obs1);
    const s2 = applyObservation(s1, obs2);

    // The newer (more recent) observation should win
    expect(getObservation(s2, 'battery.levelPct')?.value).toBe(85);
  });

  it('stores ttlMs and source on the observation', () => {
    const obs = makeObs('battery.levelPct', 80, 0, {
      ttlMs: 5000,
      source: 'bms-controller',
    });
    const state = applyObservation(emptyState(), obs);
    const stored = getObservation(state, 'battery.levelPct');
    expect(stored?.ttlMs).toBe(5000);
    expect(stored?.source).toBe('bms-controller');
  });
});

describe('getObservation', () => {
  it('returns undefined for a missing path', () => {
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 80));
    expect(getObservation(state, 'safety.estop')).toBeUndefined();
  });

  it('returns undefined on empty state', () => {
    expect(getObservation(emptyState(), 'any.path')).toBeUndefined();
  });

  it('returns the stored observation', () => {
    const obs = makeObs('localization.status', 'localized', 500);
    const state = applyObservation(emptyState(), obs);
    const result = getObservation(state, 'localization.status');
    expect(result).toMatchObject({
      path: 'localization.status',
      value: 'localized',
    });
  });

  it('returns the most recent observation after multiple updates', () => {
    // Stagger ageMs so each observation has a genuinely newer observedAt.
    // Call order is the tiebreaker when observedAt is equal.
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 100, 200));
    const s2 = applyObservation(state, makeObs('battery.levelPct', 50, 100));
    const s3 = applyObservation(s2, makeObs('battery.levelPct', 25, 0));

    expect(getObservation(s3, 'battery.levelPct')?.value).toBe(25);
  });
});
