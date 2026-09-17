/**
 * Sense SDK — core data model: NormalizedMachineState
 * @module model/state
 */

import type { TelemetryObservation } from './observation.js';

/**
 * The current normalized state of a machine.
 * Holds the latest observation for each path.
 */
export interface NormalizedMachineState {
  /**
   * Map from observation path → latest observation.
   * Only one observation per path is stored (latest wins).
   */
  readonly observations: ReadonlyMap<string, TelemetryObservation>;

  /** ISO 8601 timestamp of the last state update. */
  readonly updatedAt: string;

  /** ISO 8601 timestamp of the most recent observation's observedAt. */
  readonly latestObservationAt: string;

  /**
   * Monotonic global counter incremented each time applyObservation
   * produces a newer state (used to tiebreak equal observedAt timestamps).
   */
  readonly _version: number;
}

/**
 * Builds an updated NormalizedMachineState from the current state
 * and a new observation. The new observation wins when its observedAt
 * is strictly newer, or when observedAt is equal (call order wins).
 */
export function applyObservation(
  state: NormalizedMachineState,
  observation: TelemetryObservation,
): NormalizedMachineState {
  const existing = state.observations.get(observation.path);

  // Discard incoming if existing.observedAt is strictly newer
  if (existing !== undefined && observation.observedAt < existing.observedAt) {
    return state;
  }

  // When observedAt is equal the new call always wins (call order wins over same-ms data)
  // (no extra check needed — the early-return above is the only discard path)

  const next = new Map(state.observations);
  next.set(observation.path, observation);

  const latestObservedMs = Math.max(
    Date.parse(state.latestObservationAt),
    Date.parse(observation.observedAt),
  );

  return {
    observations: next,
    updatedAt: new Date().toISOString(),
    latestObservationAt: new Date(latestObservedMs).toISOString(),
    _version: state._version + 1,
  };
}

/**
 * Returns the observation for a given path, or undefined if absent.
 */
export function getObservation(
  state: NormalizedMachineState,
  path: string,
): TelemetryObservation | undefined {
  return state.observations.get(path);
}

/**
 * Returns a new empty NormalizedMachineState.
 */
export function emptyState(): NormalizedMachineState {
  const now = new Date().toISOString();
  return {
    observations: new Map(),
    updatedAt: now,
    latestObservationAt: now,
    _version: 0,
  };
}
