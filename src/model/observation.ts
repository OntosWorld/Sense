/**
 * Sense SDK — core data model: TelemetryObservation
 * @module model/observation
 */

import type { SchemaVersion } from '../schema/versions.js';
import { InvalidTimestampError, InvalidNumericValueError } from '../errors/index.js';

export const SCHEMA_VERSION: SchemaVersion = '1.0';

/**
 * A single telemetry observation from a machine.
 * Produced by adapters and consumed by the state engine.
 */
export interface TelemetryObservation<T = unknown> {
  /**
   * Dot-notation path identifying this observation.
   * e.g. "battery.levelPct", "localization.pose.x"
   */
  path: string;

  /** The observed value. May be any JSON-compatible type. */
  value: T;

  /**
   * ISO 8601 timestamp of when the observation was made at the source.
   * Preserved exactly — never overwritten by receive time.
   */
  observedAt: string;

  /**
   * ISO 8601 timestamp of when the observation was received by Sense.
   * Optional; useful when observation and receipt are separated in time.
   */
  receivedAt?: string;

  /**
   * Identifier of the data source (adapter, sensor, service).
   * Useful for traceability and debugging.
   */
  source?: string;

  /**
   * Maximum age in milliseconds before this observation is considered stale.
   * Optional; when absent the observation never expires on age alone.
   */
  ttlMs?: number;
}

/**
 * Validates the structural shape of a raw observation object.
 * Returns the validated observation or throws a descriptive error.
 */
export function validateObservation(raw: unknown): TelemetryObservation {
  if (raw === null || raw === undefined) {
    throw new InvalidTimestampError(String(raw), 'Observation cannot be null or undefined.');
  }
  if (typeof raw !== 'object') {
    throw new InvalidTimestampError(String(raw), 'Observation must be an object.');
  }

  const obj = raw as Record<string, unknown>;

  if (typeof obj['path'] !== 'string' || obj['path'].length === 0) {
    throw new InvalidTimestampError(
      String(obj['path']),
      'Observation path must be a non-empty string.',
    );
  }

  if (!/^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)*$/.test(obj['path'] as string)) {
    throw new InvalidTimestampError(
      obj['path'] as string,
      'Path must use dot-notation (e.g. "battery.levelPct").',
    );
  }

  // Validate observedAt is a valid ISO 8601 date
  const observedAt = obj['observedAt'];
  if (typeof observedAt !== 'string') {
    throw new InvalidTimestampError(String(observedAt), 'observedAt must be an ISO 8601 string.');
  }
  const parsed = Date.parse(observedAt);
  if (Number.isNaN(parsed)) {
    throw new InvalidTimestampError(observedAt, 'observedAt is not a valid ISO 8601 date.');
  }

  // Optionally validate receivedAt
  if (obj['receivedAt'] !== undefined && typeof obj['receivedAt'] !== 'string') {
    throw new InvalidTimestampError(
      String(obj['receivedAt']),
      'receivedAt must be an ISO 8601 string.',
    );
  }
  if (obj['receivedAt'] !== undefined) {
    const receivedParsed = Date.parse(obj['receivedAt'] as string);
    if (Number.isNaN(receivedParsed)) {
      throw new InvalidTimestampError(
        obj['receivedAt'] as string,
        'receivedAt is not a valid ISO 8601 date.',
      );
    }
  }

  // Optionally validate ttlMs
  if (obj['ttlMs'] !== undefined) {
    if (typeof obj['ttlMs'] !== 'number' || obj['ttlMs'] < 0 || !Number.isFinite(obj['ttlMs'])) {
      throw new InvalidNumericValueError(obj['path'] as string, obj['ttlMs']);
    }
  }

  return obj as unknown as TelemetryObservation;
}

/**
 * Returns true if the observation's age exceeds its TTL.
 * Age is calculated from observedAt to the given evaluation time.
 */
export function isStale(observation: TelemetryObservation, evaluationTimeMs: number): boolean {
  if (observation.ttlMs === undefined) {
    return false;
  }
  const observedMs = Date.parse(observation.observedAt);
  const ageMs = evaluationTimeMs - observedMs;
  return ageMs > observation.ttlMs;
}

/**
 * Returns the age of an observation in milliseconds at the given evaluation time.
 */
export function observationAgeMs(
  observation: TelemetryObservation,
  evaluationTimeMs: number,
): number {
  return evaluationTimeMs - Date.parse(observation.observedAt);
}
