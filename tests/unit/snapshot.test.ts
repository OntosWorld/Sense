/**
 * Sense SDK — snapshot unit tests
 * @module tests/unit/snapshot
 */

import { describe, expect, it } from 'vitest';
import { buildSnapshot, evaluateFreshness } from '../../src/model/snapshot.js';
import { emptyState, applyObservation } from '../../src/model/state.js';
import type { TelemetryObservation } from '../../src/model/observation.js';

function makeObs(path: string, value: unknown, ageMs = 0, ttlMs?: number): TelemetryObservation {
  return {
    path,
    value,
    observedAt: new Date(Date.now() - ageMs).toISOString(),
    source: 'test',
    ...(ttlMs !== undefined ? { ttlMs } : {}),
  };
}

describe('buildSnapshot', () => {
  it('creates a snapshot with schema version', () => {
    const state = emptyState();
    const snapshot = buildSnapshot(state, 'robot-001');

    expect(snapshot.schemaVersion).toBe('1.0');
  });

  it('includes machineRef', () => {
    const state = emptyState();
    const snapshot = buildSnapshot(state, 'robot-001');

    expect(snapshot.machineRef).toBe('robot-001');
  });

  it('includes observations as a Record keyed by path', () => {
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 80));
    const snapshot = buildSnapshot(state, 'robot-001');

    expect(typeof snapshot.observations).toBe('object');
    expect((snapshot.observations as Record<string, unknown>)['battery.levelPct']).toMatchObject({
      value: 80,
    });
  });

  it('includes timestamp', () => {
    const before = Date.now();
    const state = emptyState();
    const snapshot = buildSnapshot(state, 'robot-001');
    const after = Date.now();

    const ts = Date.parse(snapshot.timestamp);
    expect(ts).toBeGreaterThanOrEqual(before);
    expect(ts).toBeLessThanOrEqual(after);
  });

  it('serializes to plain JSON-compatible object', () => {
    const state = applyObservation(emptyState(), makeObs('safety.estop', false));
    const snapshot = buildSnapshot(state, 'robot-001');

    const json = JSON.stringify(snapshot);
    const parsed = JSON.parse(json);

    expect(parsed.schemaVersion).toBe('1.0');
    expect(parsed.machineRef).toBe('robot-001');
    expect(parsed.observations['safety.estop']).toMatchObject({ value: false });
  });

  it('includes peaqDid when provided', () => {
    const state = emptyState();
    const snapshot = buildSnapshot(state, 'robot-001', 'did:peaq:0x123');

    expect(snapshot.peaqDid).toBe('did:peaq:0x123');
  });

  it('omits peaqDid when not provided', () => {
    const state = emptyState();
    const snapshot = buildSnapshot(state, 'robot-001');

    expect(Object.prototype.hasOwnProperty.call(snapshot, 'peaqDid')).toBe(false);
  });

  it('excludes redacted paths from observations', () => {
    const state = applyObservation(
      applyObservation(emptyState(), makeObs('battery.levelPct', 80)),
      makeObs('safety.estop', false),
    );
    const snapshot = buildSnapshot(state, 'robot-001', undefined, ['safety.estop']);

    expect((snapshot.observations as Record<string, unknown>)['battery.levelPct']).toBeDefined();
    expect((snapshot.observations as Record<string, unknown>)['safety.estop']).toBeUndefined();
    expect(snapshot.redactedPaths).toContain('safety.estop');
  });

  it('omits redactedPaths when nothing is redacted', () => {
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 80));
    const snapshot = buildSnapshot(state, 'robot-001');

    expect(Object.prototype.hasOwnProperty.call(snapshot, 'redactedPaths')).toBe(false);
  });

  it('includes metadata when provided', () => {
    const state = emptyState();
    const snapshot = buildSnapshot(state, 'robot-001', undefined, undefined, {
      deploymentId: 'deploy-1',
    });

    expect(snapshot.metadata).toEqual({ deploymentId: 'deploy-1' });
  });

  it('excludes fields not in the schema', () => {
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 80));
    // @ts-expect-error — deliberately passing extra fields to ensure they're dropped
    const snapshot = buildSnapshot(state, 'robot-001', undefined, undefined, undefined, {
      _internal: 'should be dropped',
    } as Record<string, unknown>);

    const json = JSON.stringify(snapshot);
    expect(json).not.toContain('_internal');
  });
});

describe('evaluateFreshness', () => {
  it('marks fresh observation as fresh', () => {
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 80, 200, 5000));
    const summary = evaluateFreshness(state, Date.now());

    expect(summary.allFresh).toBe(true);
  });

  it('marks partially stale observation as not all fresh', () => {
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 80, 7000, 5000));
    const summary = evaluateFreshness(state, Date.now());

    expect(summary.allFresh).toBe(false);
  });

  it('marks all-stale observation as not all fresh', () => {
    const state = applyObservation(
      applyObservation(emptyState(), makeObs('a', 1, 9000, 5000)),
      makeObs('b', 2, 11000, 5000),
    );
    const summary = evaluateFreshness(state, Date.now());

    expect(summary.allFresh).toBe(false);
    expect(summary.observations).toHaveLength(2);
    expect(summary.observations[0]!.isFresh).toBe(false);
    expect(summary.observations[1]!.isFresh).toBe(false);
  });

  it('returns all-fresh=true for empty state', () => {
    const state = emptyState();
    const summary = evaluateFreshness(state, Date.now());

    expect(summary.allFresh).toBe(true);
    expect(summary.observations).toHaveLength(0);
  });

  it('returns all-fresh=true when observations have no ttl', () => {
    const state = applyObservation(emptyState(), makeObs('battery.levelPct', 80, 0, undefined));
    const summary = evaluateFreshness(state, Date.now());

    expect(summary.allFresh).toBe(true);
    expect(summary.observations[0]!.isFresh).toBe(true);
  });

  it('records per-observation freshness details', () => {
    const state = applyObservation(emptyState(), makeObs('fresh.path', 1, 0, 10_000));
    const s2 = applyObservation(state, makeObs('stale.path', 2, 8000, 5000));
    const summary = evaluateFreshness(s2, Date.now());

    expect(summary.observations).toHaveLength(2);
    const freshObs = summary.observations.find((o) => o.path === 'fresh.path')!;
    const staleObs = summary.observations.find((o) => o.path === 'stale.path')!;
    expect(freshObs.isFresh).toBe(true);
    expect(staleObs.isFresh).toBe(false);
  });

  it('includes ageMs and ttlMs in per-observation details', () => {
    const state = applyObservation(emptyState(), makeObs('a', 1, 2000, 5000));
    const summary = evaluateFreshness(state, Date.now());

    expect(summary.observations[0]!.ageMs).toBeGreaterThanOrEqual(2000);
    expect(summary.observations[0]!.ttlMs).toBe(5000);
    expect(summary.observations[0]!.observedAt).toBeTruthy();
  });
});
