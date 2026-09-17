/**
 * Sense SDK — capability evaluation engine
 * @module engine/evaluator
 */

import type { NormalizedMachineState } from '../model/state.js';
import type { CapabilityDefinition } from './capability.js';
import type { Rule, RuleResult } from '../rules/index.js';
import { evaluateRule } from '../rules/index.js';

/**
 * Possible status of a capability evaluation.
 *
 * AVAILABLE — all mandatory evidence exists, is fresh, and mandatory constraints pass.
 * DEGRADED  — mandatory constraints permit the capability, but some degradation rules are active.
 * UNAVAILABLE — one or more mandatory constraints fail.
 * UNKNOWN   — required evidence is missing, invalid, cannot be interpreted, or is too stale.
 */
export type CapabilityStatus = 'AVAILABLE' | 'DEGRADED' | 'UNAVAILABLE' | 'UNKNOWN';

/**
 * Reason codes for UNKNOWN status.
 * Used to give programmatic access to why a capability is unknown.
 */
export type UnknownReasonCode =
  'MISSING_EVIDENCE' | 'STALE_EVIDENCE' | 'INVALID_VALUE' | 'EVALUATION_ERROR';

/**
 * Result of evaluating a single capability.
 * This result is immutable once produced.
 */
export interface CapabilityEvaluationResult {
  /** The capability name. */
  readonly name: string;

  /** The computed status. */
  readonly status: CapabilityStatus;

  /**
   * Human-readable explanation.
   * Always present; never empty.
   */
  readonly explanation: string;

  /**
   * Reason code for UNKNOWN status, undefined otherwise.
   */
  readonly unknownReason?: UnknownReasonCode;

  /**
   * Reason code for UNAVAILABLE status, undefined otherwise.
   */
  readonly unavailableReason?: string;

  /**
   * Rule results for all mandatory rules.
   */
  readonly mandatoryRuleResults: readonly RuleResult[];

  /**
   * Rule results for all degradation rules.
   */
  readonly degradationRuleResults: readonly RuleResult[];

  /**
   * Paths that contributed to the UNKNOWN or UNAVAILABLE status.
   */
  readonly failedPaths: readonly string[];

  /** ISO 8601 timestamp of this evaluation. */
  readonly evaluatedAt: string;
}

/**
 * Internal unknown reason classification helper.
 */
function classifyUnknown(
  mandatoryResults: readonly RuleResult[],
  allMissingPaths: Set<string>,
): UnknownReasonCode {
  // If any mandatory rule references a missing path, classify as missing
  for (const r of mandatoryResults) {
    if (!r.passed && r.path !== undefined && allMissingPaths.has(r.path)) {
      return 'MISSING_EVIDENCE';
    }
  }
  // Stale evidence
  for (const r of mandatoryResults) {
    if (!r.passed && r.reason.toLowerCase().includes('stale')) {
      return 'STALE_EVIDENCE';
    }
  }
  return 'MISSING_EVIDENCE';
}

/**
 * Evaluates a single capability definition against machine state.
 * This is the core hot-path operation — no network calls.
 *
 * @param capability - The capability definition to evaluate
 * @param state - Current machine state
 * @param evaluationTimeMs - Evaluation time in milliseconds (defaults to Date.now())
 */
export function evaluateCapability(
  capability: CapabilityDefinition,
  state: NormalizedMachineState,
  evaluationTimeMs: number = Date.now(),
): CapabilityEvaluationResult {
  const evaluatedAt = new Date(evaluationTimeMs).toISOString();

  // Collect all paths referenced by mandatory rules
  const mandatoryPaths = collectPathsFromRules(capability.mandatoryRules);
  const degradationPaths = collectPathsFromRules(capability.degradationRules);
  const allReferencedPaths = new Set([...mandatoryPaths, ...degradationPaths]);

  // Check for missing evidence
  const missingPaths: string[] = [];
  const stalePaths: string[] = [];

  for (const path of allReferencedPaths) {
    const obs = state.observations.get(path);
    if (obs === undefined) {
      missingPaths.push(path);
    } else if (obs.ttlMs !== undefined) {
      const ageMs = evaluationTimeMs - Date.parse(obs.observedAt);
      if (ageMs > obs.ttlMs) {
        stalePaths.push(path);
      }
    }
  }

  // If mandatory evidence is entirely absent or stale → UNKNOWN
  const missingMandatory = mandatoryPaths.filter((p) => missingPaths.includes(p));
  const staleMandatory = mandatoryPaths.filter((p) => stalePaths.includes(p));

  if (missingMandatory.length > 0 || staleMandatory.length > 0) {
    const reasonPaths = staleMandatory.length > 0 ? staleMandatory : missingMandatory;
    const reasonCode = classifyUnknown([], new Set(reasonPaths));

    return {
      name: capability.name,
      status: 'UNKNOWN',
      explanation:
        `${capability.name} is UNKNOWN because required evidence is unavailable: ` +
        `${reasonPaths.map((p) => `"${p}"`).join(', ')}. ` +
        (staleMandatory.length > 0 ? 'Evidence is stale.' : 'Evidence is missing.'),
      unknownReason: reasonCode,
      mandatoryRuleResults: [],
      degradationRuleResults: [],
      failedPaths: reasonPaths,
      evaluatedAt,
    };
  }

  // Evaluate all mandatory rules
  const mandatoryResults: RuleResult[] = [];
  let allMandatoryPass = true;
  let unavailableReason = '';

  for (const rule of capability.mandatoryRules) {
    let result: RuleResult;
    try {
      result = evaluateRule(rule, state, evaluationTimeMs);
    } catch (err) {
      // Evaluation error → UNKNOWN
      return {
        name: capability.name,
        status: 'UNKNOWN',
        explanation: `${capability.name} evaluation error: ${err instanceof Error ? err.message : String(err)}.`,
        unknownReason: 'EVALUATION_ERROR',
        mandatoryRuleResults: [],
        degradationRuleResults: [],
        failedPaths: [],
        evaluatedAt,
      };
    }
    mandatoryResults.push(result);
    if (!result.passed) {
      // Intercept fresh rule failures on stale evidence → UNKNOWN
      // The pre-check gate uses ttlMs from observations; fresh() uses maxAgeMs.
      // When evidence passes ttlMs but fails fresh() maxAgeMs, route to UNKNOWN
      // rather than letting it fall through to UNAVAILABLE.
      if (rule.type === 'fresh') {
        const failedPaths = result.path !== undefined ? [result.path] : [];
        return {
          name: capability.name,
          status: 'UNKNOWN',
          explanation: `${capability.name} is UNKNOWN. ${result.reason}`,
          unknownReason: 'STALE_EVIDENCE',
          mandatoryRuleResults: mandatoryResults,
          degradationRuleResults: [],
          failedPaths,
          evaluatedAt,
        };
      }
      allMandatoryPass = false;
      unavailableReason = result.reason;
    }
  }

  // If any mandatory rule fails → UNAVAILABLE
  if (!allMandatoryPass) {
    const failedPaths = mandatoryResults
      .filter((r) => !r.passed && r.path !== undefined)
      .map((r) => r.path as string);

    return {
      name: capability.name,
      status: 'UNAVAILABLE',
      explanation: `${capability.name} is UNAVAILABLE. ${unavailableReason}`,
      unavailableReason: unavailableReason,
      mandatoryRuleResults: mandatoryResults,
      degradationRuleResults: [],
      failedPaths,
      evaluatedAt,
    };
  }

  // All mandatory pass → evaluate degradation rules
  const degradationResults: RuleResult[] = [];
  let anyDegradationFails = false;

  for (const rule of capability.degradationRules) {
    let result: RuleResult;
    try {
      result = evaluateRule(rule, state, evaluationTimeMs);
    } catch {
      // Degradation rule errors are non-fatal; treat as pass
      result = { passed: true, reason: 'Could not evaluate degradation rule.' };
    }
    degradationResults.push(result);
    if (!result.passed) anyDegradationFails = true;
  }

  const failedDegradationPaths = degradationResults
    .filter((r) => !r.passed && r.path !== undefined)
    .map((r) => r.path as string);

  return {
    name: capability.name,
    status: anyDegradationFails ? 'DEGRADED' : 'AVAILABLE',
    explanation: anyDegradationFails
      ? `${capability.name} is DEGRADED. Mandatory constraints pass, but degradation active: ${degradationResults
          .filter((r) => !r.passed)
          .map((r) => r.reason)
          .join(' ')}`
      : `${capability.name} is AVAILABLE.`,
    mandatoryRuleResults: mandatoryResults,
    degradationRuleResults: degradationResults,
    failedPaths: failedDegradationPaths,
    evaluatedAt,
  };
}

/**
 * Collects all observation paths referenced by a list of rules (recursive).
 */
function collectPathsFromRules(rules: readonly Rule[]): string[] {
  const paths: string[] = [];
  for (const rule of rules) {
    collectPaths(rule, paths);
  }
  return paths;
}

function collectPaths(rule: Rule, paths: string[]): void {
  switch (rule.type) {
    case 'equals':
    case 'notEquals':
    case 'greaterThan':
    case 'greaterThanOrEqual':
    case 'lessThan':
    case 'lessThanOrEqual':
    case 'exists':
    case 'inSet':
    case 'fresh':
      paths.push(rule.path);
      break;
    case 'and':
    case 'or':
      for (const r of rule.rules) collectPaths(r, paths);
      break;
    case 'not':
      collectPaths(rule.rule, paths);
      break;
  }
}
