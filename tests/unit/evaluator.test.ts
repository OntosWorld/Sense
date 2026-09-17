/**
 * Unit tests — capability evaluator
 */
import { describe, it, expect } from 'vitest';
import { emptyState, applyObservation } from '../../src/model/state.js';
import { evaluateCapability } from '../../src/engine/evaluator.js';
import { defineCapability } from '../../src/engine/capability.js';
import { equals, gte, lessThanOrEqual, fresh, exists } from '../../src/rules/index.js';

const NOW_MS = Date.parse('2024-01-01T12:00:00.000Z');

function makeState(observations: Record<string, unknown>, ageMs = 0) {
  let state = emptyState();
  const observedAt = new Date(NOW_MS - ageMs).toISOString();
  for (const [path, value] of Object.entries(observations)) {
    state = applyObservation(state, {
      path,
      value,
      observedAt,
      ttlMs: ageMs > 0 ? ageMs + 1 : undefined,
    });
  }
  return state;
}

function makeStaleState(observations: Record<string, unknown>, ttlMs: number) {
  let state = emptyState();
  const observedAt = new Date(NOW_MS - ttlMs - 1000).toISOString();
  for (const [path, value] of Object.entries(observations)) {
    state = applyObservation(state, {
      path,
      value,
      observedAt,
      ttlMs, // will be stale
    });
  }
  return state;
}

describe('evaluateCapability', () => {
  describe('AVAILABLE', () => {
    it('returns AVAILABLE when all mandatory rules pass', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [equals('safety.estop', false), gte('battery.levelPct', 20)],
      });
      const state = makeState({
        'safety.estop': false,
        'battery.levelPct': 78,
      });

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.status).toBe('AVAILABLE');
      expect(result.mandatoryRuleResults.every((r) => r.passed)).toBe(true);
    });

    it('returns AVAILABLE with DEGRADED status when degradation rules fail', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [gte('battery.levelPct', 20)],
        degradationRules: [lessThanOrEqual('battery.levelPct', 50)],
      });
      const state = makeState({ 'battery.levelPct': 78 });

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.status).toBe('DEGRADED');
      expect(result.degradationRuleResults.some((r) => !r.passed)).toBe(true);
    });
  });

  describe('UNAVAILABLE', () => {
    it('returns UNAVAILABLE when a mandatory rule fails', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [equals('safety.estop', false), gte('battery.levelPct', 20)],
      });
      const state = makeState({
        'safety.estop': false,
        'battery.levelPct': 10, // below threshold
      });

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.status).toBe('UNAVAILABLE');
      expect(result.unavailableReason).toBeDefined();
    });
  });

  describe('UNKNOWN', () => {
    it('returns UNKNOWN when a required observation is missing', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [
          equals('safety.estop', false),
          gte('battery.levelPct', 20), // missing
        ],
      });
      const state = makeState({ 'safety.estop': false });

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.status).toBe('UNKNOWN');
      expect(result.unknownReason).toBe('MISSING_EVIDENCE');
      expect(result.failedPaths).toContain('battery.levelPct');
    });

    it('returns UNKNOWN when a required observation is stale', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [equals('safety.estop', false), gte('battery.levelPct', 20)],
      });
      // State with stale battery observation
      const state = makeStaleState(
        { 'safety.estop': false, 'battery.levelPct': 78 },
        5_000, // TTL
      );

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.status).toBe('UNKNOWN');
    });

    it('returns UNKNOWN when fresh rule is violated', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [
          equals('safety.estop', false),
          fresh('localization.pose', { maxAgeMs: 1_000 }),
        ],
      });
      // Observation is 3 seconds old but maxAgeMs is 1 second
      const state = makeState(
        { 'safety.estop': false, 'localization.pose': { x: 1, y: 2 } },
        3_000,
      );

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.status).toBe('UNKNOWN');
    });
  });

  describe('DEGRADED', () => {
    it('returns DEGRADED when mandatory pass but degradation fails', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [gte('battery.levelPct', 20)],
        degradationRules: [lessThanOrEqual('battery.levelPct', 50)],
      });
      const state = makeState({ 'battery.levelPct': 78 });

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.status).toBe('DEGRADED');
    });
  });

  describe('explanation', () => {
    it('always has a non-empty explanation', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [equals('safety.estop', false)],
      });
      const state = makeState({ 'safety.estop': false });

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.explanation.length).toBeGreaterThan(0);
    });
  });

  describe('evaluatedAt', () => {
    it('uses the provided evaluation time', () => {
      const cap = defineCapability({
        name: 'test.capability',
        mandatoryRules: [equals('safety.estop', false)],
      });
      const state = makeState({ 'safety.estop': false });

      const result = evaluateCapability(cap, state, NOW_MS);

      expect(result.evaluatedAt).toBe(new Date(NOW_MS).toISOString());
    });
  });
});
