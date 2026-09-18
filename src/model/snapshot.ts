/**
 * Sense SDK — core data model: ContextSnapshot
 * @module model/snapshot
 */

import type { NormalizedMachineState } from './state.js';
import { SCHEMA_VERSION } from './observation.js';

export { SCHEMA_VERSION as CONTEXT_SCHEMA_VERSION } from './observation.js';

/**
 * A publishable, serialized snapshot of machine context.
 * Includes a schema version for cross-language compatibility.
 */
export interface ContextSnapshot {
  /** Always included. Identifies the schema used for this snapshot. */
  schemaVersion: '1.0';

  /** Developer-assigned machine identifier. */
  machineRef: string;

  /** Optional peaq decentralized identifier. */
  peaqDid?: string;

  /** ISO 8601 timestamp when this snapshot was evaluated. */
  timestamp: string;

  /** ISO 8601 timestamp of the most recent observation in this snapshot. */
  latestObservationAt: string;

  /**
   * All current observations keyed by path.
   * Private/sensitive fields may be redacted before publishing.
   */
  observations: Record<string, unknown>;

  /** List of paths that were omitted due to redaction. */
  redactedPaths?: string[];

  /** Optional developer-provided metadata. */
  metadata?: Record<string, unknown>;
}

/**
 * Builds a ContextSnapshot from the current machine state.
 *
 * @param state - The current NormalizedMachineState
 * @param machineRef - Developer-assigned machine identifier
 * @param peaqDid - Optional peaq DID
 * @param redactPaths - Optional denylist: paths to exclude from the snapshot
 * @param metadata - Optional additional metadata
 * @param allowPaths - Optional allowlist: if set, only these paths are included (denylist is applied on top)
 */
export function buildSnapshot(
  state: NormalizedMachineState,
  machineRef: string,
  peaqDid?: string,
  redactPaths?: readonly string[],
  metadata?: Record<string, unknown>,
  allowPaths?: readonly string[],
): ContextSnapshot {
  const redacted: string[] = [];
  const observations: Record<string, unknown> = {};

  const redactSet = new Set<string>(redactPaths ?? []);
  const allowSet = allowPaths ? new Set<string>(allowPaths) : null;

  for (const [path, obs] of state.observations) {
    // Apply allowlist: skip paths not in the allowlist (when one is set)
    if (allowSet !== null && !allowSet.has(path)) continue;

    if (redactSet.has(path)) {
      redacted.push(path);
    } else {
      // Store the full observation so consumers have observedAt, source, ttlMs
      observations[path] = obs;
    }
  }

  return {
    schemaVersion: SCHEMA_VERSION,
    machineRef,
    ...(peaqDid !== undefined && { peaqDid }),
    timestamp: new Date().toISOString(),
    latestObservationAt: state.latestObservationAt,
    observations,
    ...(redacted.length > 0 && { redactedPaths: redacted }),
    ...(metadata !== undefined && { metadata }),
  };
}

/**
 * Serializable representation of a single observation's freshness status.
 */
export interface ObservationFreshness {
  path: string;
  observedAt: string;
  ageMs: number;
  ttlMs?: number;
  isFresh: boolean;
}

/**
 * Freshness summary for all observations in a snapshot.
 */
export interface FreshnessSummary {
  timestamp: string;
  observations: ObservationFreshness[];
  allFresh: boolean;
}

/**
 * Evaluates freshness of all observations in a state at a given time.
 */
export function evaluateFreshness(
  state: NormalizedMachineState,
  evaluationTimeMs: number,
): FreshnessSummary {
  const entries: ObservationFreshness[] = [];
  let allFresh = true;

  for (const [path, obs] of state.observations) {
    const ageMs = evaluationTimeMs - Date.parse(obs.observedAt);
    const isFresh = obs.ttlMs === undefined || ageMs <= obs.ttlMs;
    if (!isFresh) allFresh = false;
    entries.push({
      path,
      observedAt: obs.observedAt,
      ageMs,
      ...(obs.ttlMs !== undefined && { ttlMs: obs.ttlMs }),
      isFresh,
    });
  }

  return {
    timestamp: new Date(evaluationTimeMs).toISOString(),
    observations: entries,
    allFresh,
  };
}
