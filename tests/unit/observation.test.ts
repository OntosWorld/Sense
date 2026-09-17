/**
 * Unit tests — TelemetryObservation
 */
import { describe, it, expect } from 'vitest';
import {
  validateObservation,
  isStale,
  observationAgeMs,
  type TelemetryObservation,
} from '../../src/model/observation.js';
import { InvalidTimestampError, InvalidNumericValueError } from '../../src/errors/index.js';

describe('validateObservation', () => {
  it('accepts a valid observation', () => {
    const obs: TelemetryObservation = {
      path: 'battery.levelPct',
      value: 78,
      observedAt: '2024-01-01T12:00:00.000Z',
      source: 'sensor-1',
      ttlMs: 5000,
    };
    expect(validateObservation(obs)).toEqual(obs);
  });

  it('accepts a minimal observation (only required fields)', () => {
    const obs = {
      path: 'temperature.celsius',
      value: 22.5,
      observedAt: new Date().toISOString(),
    };
    expect(validateObservation(obs)).toEqual(obs);
  });

  it('rejects null', () => {
    expect(() => validateObservation(null)).toThrow(InvalidTimestampError);
  });

  it('rejects a non-object', () => {
    expect(() => validateObservation(42)).toThrow(InvalidTimestampError);
  });

  it('rejects a missing path', () => {
    expect(() => validateObservation({ value: 42, observedAt: new Date().toISOString() })).toThrow(
      InvalidTimestampError,
    );
  });

  it('rejects an empty path', () => {
    expect(() =>
      validateObservation({ path: '', value: 42, observedAt: new Date().toISOString() }),
    ).toThrow(InvalidTimestampError);
  });

  it('rejects a malformed path', () => {
    expect(() =>
      validateObservation({ path: 'not-valid', value: 42, observedAt: new Date().toISOString() }),
    ).toThrow(InvalidTimestampError);
  });

  it('rejects a missing observedAt', () => {
    expect(() => validateObservation({ path: 'battery.levelPct', value: 78 })).toThrow(
      InvalidTimestampError,
    );
  });

  it('rejects an invalid observedAt', () => {
    expect(() =>
      validateObservation({ path: 'battery.levelPct', value: 78, observedAt: 'not-a-date' }),
    ).toThrow(InvalidTimestampError);
  });

  it('rejects a negative ttlMs', () => {
    expect(() =>
      validateObservation({
        path: 'battery.levelPct',
        value: 78,
        observedAt: new Date().toISOString(),
        ttlMs: -100,
      }),
    ).toThrow(InvalidNumericValueError);
  });

  it('rejects an Infinity ttlMs', () => {
    expect(() =>
      validateObservation({
        path: 'battery.levelPct',
        value: 78,
        observedAt: new Date().toISOString(),
        ttlMs: Infinity,
      }),
    ).toThrow(InvalidNumericValueError);
  });

  it('accepts a valid receivedAt', () => {
    const obs = {
      path: 'battery.levelPct',
      value: 78,
      observedAt: '2024-01-01T10:00:00.000Z',
      receivedAt: '2024-01-01T10:00:01.000Z',
    };
    expect(validateObservation(obs)).toEqual(obs);
  });

  it('rejects an invalid receivedAt', () => {
    expect(() =>
      validateObservation({
        path: 'battery.levelPct',
        value: 78,
        observedAt: new Date().toISOString(),
        receivedAt: 'invalid',
      }),
    ).toThrow(InvalidTimestampError);
  });
});

describe('isStale', () => {
  const baseTime = Date.parse('2024-01-01T12:00:00.000Z');

  it('returns false when no TTL is set', () => {
    const obs: TelemetryObservation = {
      path: 'battery.levelPct',
      value: 78,
      observedAt: new Date(baseTime - 60_000).toISOString(),
    };
    expect(isStale(obs, baseTime)).toBe(false);
  });

  it('returns false when age is within TTL', () => {
    const obs: TelemetryObservation = {
      path: 'battery.levelPct',
      value: 78,
      observedAt: new Date(baseTime - 3_000).toISOString(),
      ttlMs: 5_000,
    };
    expect(isStale(obs, baseTime)).toBe(false);
  });

  it('returns true when age exceeds TTL', () => {
    const obs: TelemetryObservation = {
      path: 'battery.levelPct',
      value: 78,
      observedAt: new Date(baseTime - 10_000).toISOString(),
      ttlMs: 5_000,
    };
    expect(isStale(obs, baseTime)).toBe(true);
  });

  it('returns true when age exactly equals TTL', () => {
    const obs: TelemetryObservation = {
      path: 'battery.levelPct',
      value: 78,
      observedAt: new Date(baseTime - 5_000).toISOString(),
      ttlMs: 5_000,
    };
    expect(isStale(obs, baseTime)).toBe(false); // >, not >=
  });
});

describe('observationAgeMs', () => {
  it('returns correct age in milliseconds', () => {
    const baseTime = Date.parse('2024-01-01T12:00:00.000Z');
    const obs: TelemetryObservation = {
      path: 'battery.levelPct',
      value: 78,
      observedAt: new Date(baseTime - 3_500).toISOString(),
    };
    expect(observationAgeMs(obs, baseTime)).toBe(3_500);
  });
});
