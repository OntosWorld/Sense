/**
 * Sense SDK — capability rules
 * @module rules
 */

import type { NormalizedMachineState } from '../model/state.js';
import type { TelemetryObservation } from '../model/observation.js';
import { getObservation } from '../model/state.js';
import { InvalidRuleError } from '../errors/index.js';

// ---------------------------------------------------------------------------
// Primitive rule types
// ---------------------------------------------------------------------------

/** Severity of a rule within a capability definition. */
export type RuleSeverity = 'blocking' | 'degradation';

/** Narrowing level for fresh() rules. */
export interface FreshOptions {
  maxAgeMs: number;
}

/** Result of evaluating a single rule against machine state. */
export interface RuleResult {
  /** True if the rule passed. */
  passed: boolean;

  /** Human-readable explanation of why the rule passed or failed. */
  reason: string;

  /** The path this rule evaluated, if any. */
  path?: string;
}

/** A single evaluable rule. */
export type Rule =
  | EqualsRule
  | NotEqualsRule
  | GreaterThanRule
  | GreaterThanOrEqualRule
  | LessThanRule
  | LessThanOrEqualRule
  | ExistsRule
  | InSetRule
  | FreshRule
  | AndRule
  | OrRule
  | NotRule;

// ---------------------------------------------------------------------------
// Rule interfaces (discriminated by `type')
// ---------------------------------------------------------------------------

export interface EqualsRule {
  readonly type: 'equals';
  readonly path: string;
  readonly value: unknown;
}

export interface NotEqualsRule {
  readonly type: 'notEquals';
  readonly path: string;
  readonly value: unknown;
}

export interface GreaterThanRule {
  readonly type: 'greaterThan';
  readonly path: string;
  readonly value: number;
}

export interface GreaterThanOrEqualRule {
  readonly type: 'greaterThanOrEqual';
  readonly path: string;
  readonly value: number;
}

export interface LessThanRule {
  readonly type: 'lessThan';
  readonly path: string;
  readonly value: number;
}

export interface LessThanOrEqualRule {
  readonly type: 'lessThanOrEqual';
  readonly path: string;
  readonly value: number;
}

export interface ExistsRule {
  readonly type: 'exists';
  readonly path: string;
}

export interface InSetRule {
  readonly type: 'inSet';
  readonly path: string;
  readonly values: readonly unknown[];
}

export interface FreshRule {
  readonly type: 'fresh';
  readonly path: string;
  readonly options: FreshOptions;
}

export interface AndRule {
  readonly type: 'and';
  readonly rules: readonly Rule[];
}

export interface OrRule {
  readonly type: 'or';
  readonly rules: readonly Rule[];
}

export interface NotRule {
  readonly type: 'not';
  readonly rule: Rule;
}

// ---------------------------------------------------------------------------
// Rule constructors (public API)
// ---------------------------------------------------------------------------

function makeRule<T extends Rule>(type: T['type'], fields: Omit<T, 'type'>): T {
  return { type, ...fields } as T;
}

/** Creates an equals rule. */
export function equals(path: string, value: unknown): EqualsRule {
  return makeRule<EqualsRule>('equals', { path, value });
}

/** Creates a not-equals rule. */
export function notEquals(path: string, value: unknown): NotEqualsRule {
  return makeRule<NotEqualsRule>('notEquals', { path, value });
}

/** Creates a greater-than rule. Requires the observed value to be numeric. */
export function greaterThan(path: string, value: number): GreaterThanRule {
  return makeRule<GreaterThanRule>('greaterThan', { path, value });
}

/** Alias: gt */
export { greaterThan as gt };

/** Creates a greater-than-or-equal rule. */
export function greaterThanOrEqual(path: string, value: number): GreaterThanOrEqualRule {
  return makeRule<GreaterThanOrEqualRule>('greaterThanOrEqual', { path, value });
}

/** Alias: gte */
export { greaterThanOrEqual as gte };

/** Creates a less-than rule. */
export function lessThan(path: string, value: number): LessThanRule {
  return makeRule<LessThanRule>('lessThan', { path, value });
}

/** Alias: lt */
export { lessThan as lt };

/** Creates a less-than-or-equal rule. */
export function lessThanOrEqual(path: string, value: number): LessThanOrEqualRule {
  return makeRule<LessThanOrEqualRule>('lessThanOrEqual', { path, value });
}

/** Alias: lte */
export { lessThanOrEqual as lte };

/** Creates an exists rule. The observation must be present and not stale. */
export function exists(path: string): ExistsRule {
  return makeRule<ExistsRule>('exists', { path });
}

/** Creates an in-set rule. The observed value must be one of the provided values. */
export function inSet(path: string, values: readonly unknown[]): InSetRule {
  if (!Array.isArray(values)) {
    throw new InvalidRuleError(`inSet values must be an array, got ${typeof values}.`, { path });
  }
  return makeRule<InSetRule>('inSet', { path, values });
}

/** Creates a freshness rule. The observation must be fresh (within maxAgeMs). */
export function fresh(path: string, options: FreshOptions): FreshRule {
  if (typeof options.maxAgeMs !== 'number' || options.maxAgeMs < 0) {
    throw new InvalidRuleError(`fresh maxAgeMs must be a non-negative number.`, {
      path,
      maxAgeMs: options.maxAgeMs,
    });
  }
  return makeRule<FreshRule>('fresh', { path, options });
}

/** Creates a logical AND rule. All child rules must pass. */
export function all(rules: readonly Rule[]): AndRule {
  if (!Array.isArray(rules) || rules.length < 2) {
    throw new InvalidRuleError('all() requires at least 2 rules.', {});
  }
  return makeRule<AndRule>('and', { rules });
}

/** Alias: ALL */
export { all as ALL };

/** Creates a logical OR rule. At least one child rule must pass. */
export function any(rules: readonly Rule[]): OrRule {
  if (!Array.isArray(rules) || rules.length < 2) {
    throw new InvalidRuleError('any() requires at least 2 rules.', {});
  }
  return makeRule<OrRule>('or', { rules });
}

/** Alias: ANY */
export { any as ANY };

/** Creates a logical NOT rule. The child rule must fail. */
export function not(rule: Rule): NotRule {
  return makeRule<NotRule>('not', { rule });
}

/** Alias: NOT */
export { not as NOT };

// ---------------------------------------------------------------------------
// Rule evaluation
// ---------------------------------------------------------------------------

/**
 * Evaluates a single primitive rule against machine state at a given time.
 */
export function evaluateRule(
  rule: Rule,
  state: NormalizedMachineState,
  evaluationTimeMs: number,
): RuleResult {
  switch (rule.type) {
    case 'equals':
      return evaluateEquals(rule, state);
    case 'notEquals':
      return evaluateNotEquals(rule, state);
    case 'greaterThan':
      return evaluateGreaterThan(rule, state);
    case 'greaterThanOrEqual':
      return evaluateGreaterThanOrEqual(rule, state);
    case 'lessThan':
      return evaluateLessThan(rule, state);
    case 'lessThanOrEqual':
      return evaluateLessThanOrEqual(rule, state);
    case 'exists':
      return evaluateExists(rule, state);
    case 'inSet':
      return evaluateInSet(rule, state);
    case 'fresh':
      return evaluateFresh(rule, state, evaluationTimeMs);
    case 'and':
      return evaluateAnd(rule, state, evaluationTimeMs);
    case 'or':
      return evaluateOr(rule, state, evaluationTimeMs);
    case 'not':
      return evaluateNot(rule, state, evaluationTimeMs);
    default: {
      const _exhaustive: never = rule;
      throw new InvalidRuleError(`Unknown rule type: ${_exhaustive}`, {});
    }
  }
}

function getNumericValue(obs: TelemetryObservation, path: string): number {
  const v = obs.value;
  if (typeof v !== 'number' || !Number.isFinite(v)) {
    throw new InvalidRuleError(
      `Rule requires a numeric value at "${path}", but observed ${typeof v}.`,
      { path, value: v },
    );
  }
  return v;
}

function evaluateEquals(rule: EqualsRule, state: NormalizedMachineState): RuleResult {
  const obs = getObservation(state, rule.path);
  const passed = obs !== undefined && deepEqual(obs.value, rule.value);
  return {
    passed,
    reason: passed
      ? `"${rule.path}" equals ${JSON.stringify(rule.value)}.`
      : obs === undefined
        ? `"${rule.path}" is missing.`
        : `"${rule.path}" is ${JSON.stringify(obs.value)}, expected ${JSON.stringify(rule.value)}.`,
    path: rule.path,
  };
}

function evaluateNotEquals(rule: NotEqualsRule, state: NormalizedMachineState): RuleResult {
  const obs = getObservation(state, rule.path);
  const passed = obs !== undefined && !deepEqual(obs.value, rule.value);
  return {
    passed,
    reason: passed
      ? `"${rule.path}" is not ${JSON.stringify(rule.value)}.`
      : obs === undefined
        ? `"${rule.path}" is missing.`
        : `"${rule.path}" equals ${JSON.stringify(rule.value)}.`,
    path: rule.path,
  };
}

function evaluateGreaterThan(rule: GreaterThanRule, state: NormalizedMachineState): RuleResult {
  const obs = getObservation(state, rule.path);
  if (obs === undefined) {
    return { passed: false, reason: `"${rule.path}" is missing.`, path: rule.path };
  }
  const v = getNumericValue(obs, rule.path);
  const passed = v > rule.value;
  return {
    passed,
    reason: passed
      ? `"${rule.path}" (${v}) > ${rule.value}.`
      : `"${rule.path}" (${v}) is not > ${rule.value}.`,
    path: rule.path,
  };
}

function evaluateGreaterThanOrEqual(
  rule: GreaterThanOrEqualRule,
  state: NormalizedMachineState,
): RuleResult {
  const obs = getObservation(state, rule.path);
  if (obs === undefined) {
    return { passed: false, reason: `"${rule.path}" is missing.`, path: rule.path };
  }
  const v = getNumericValue(obs, rule.path);
  const passed = v >= rule.value;
  return {
    passed,
    reason: passed
      ? `"${rule.path}" (${v}) >= ${rule.value}.`
      : `"${rule.path}" (${v}) is not >= ${rule.value}.`,
    path: rule.path,
  };
}

function evaluateLessThan(rule: LessThanRule, state: NormalizedMachineState): RuleResult {
  const obs = getObservation(state, rule.path);
  if (obs === undefined) {
    return { passed: false, reason: `"${rule.path}" is missing.`, path: rule.path };
  }
  const v = getNumericValue(obs, rule.path);
  const passed = v < rule.value;
  return {
    passed,
    reason: passed
      ? `"${rule.path}" (${v}) < ${rule.value}.`
      : `"${rule.path}" (${v}) is not < ${rule.value}.`,
    path: rule.path,
  };
}

function evaluateLessThanOrEqual(
  rule: LessThanOrEqualRule,
  state: NormalizedMachineState,
): RuleResult {
  const obs = getObservation(state, rule.path);
  if (obs === undefined) {
    return { passed: false, reason: `"${rule.path}" is missing.`, path: rule.path };
  }
  const v = getNumericValue(obs, rule.path);
  const passed = v <= rule.value;
  return {
    passed,
    reason: passed
      ? `"${rule.path}" (${v}) <= ${rule.value}.`
      : `"${rule.path}" (${v}) is not <= ${rule.value}.`,
    path: rule.path,
  };
}

function evaluateExists(rule: ExistsRule, state: NormalizedMachineState): RuleResult {
  const obs = getObservation(state, rule.path);
  const passed = obs !== undefined;
  return {
    passed,
    reason: passed ? `"${rule.path}" exists.` : `"${rule.path}" is missing.`,
    path: rule.path,
  };
}

function evaluateInSet(rule: InSetRule, state: NormalizedMachineState): RuleResult {
  const obs = getObservation(state, rule.path);
  if (obs === undefined) {
    return { passed: false, reason: `"${rule.path}" is missing.`, path: rule.path };
  }
  const passed = rule.values.some((v) => deepEqual(obs.value, v));
  return {
    passed,
    reason: passed
      ? `"${rule.path}" is in set ${JSON.stringify(rule.values)}.`
      : `"${rule.path}" (${JSON.stringify(obs.value)}) is not in set ${JSON.stringify(rule.values)}.`,
    path: rule.path,
  };
}

function evaluateFresh(
  rule: FreshRule,
  state: NormalizedMachineState,
  evaluationTimeMs: number,
): RuleResult {
  const obs = getObservation(state, rule.path);
  if (obs === undefined) {
    return {
      passed: false,
      reason: `"${rule.path}" is missing — cannot evaluate freshness.`,
      path: rule.path,
    };
  }
  const ageMs = evaluationTimeMs - Date.parse(obs.observedAt);
  const passed = ageMs <= rule.options.maxAgeMs;
  return {
    passed,
    reason: passed
      ? `"${rule.path}" is fresh (age ${ageMs}ms <= ${rule.options.maxAgeMs}ms).`
      : `"${rule.path}" is stale (age ${ageMs}ms > ${rule.options.maxAgeMs}ms).`,
    path: rule.path,
  };
}

function evaluateAnd(
  rule: AndRule,
  state: NormalizedMachineState,
  evaluationTimeMs: number,
): RuleResult {
  const results = rule.rules.map((r) => evaluateRule(r, state, evaluationTimeMs));
  const allPassed = results.every((r) => r.passed);
  const failed = results.filter((r) => !r.passed);
  return {
    passed: allPassed,
    reason: allPassed
      ? `All ${results.length} conditions met.`
      : `Failed: ${failed.map((r) => r.reason).join('; ')}`,
  };
}

function evaluateOr(
  rule: OrRule,
  state: NormalizedMachineState,
  evaluationTimeMs: number,
): RuleResult {
  const results = rule.rules.map((r) => evaluateRule(r, state, evaluationTimeMs));
  const anyPassed = results.some((r) => r.passed);
  const passedCount = results.filter((r) => r.passed).length;
  return {
    passed: anyPassed,
    reason: anyPassed
      ? `${passedCount} of ${results.length} conditions met.`
      : `None of ${results.length} conditions met.`,
  };
}

function evaluateNot(
  rule: NotRule,
  state: NormalizedMachineState,
  evaluationTimeMs: number,
): RuleResult {
  const inner = evaluateRule(rule.rule, state, evaluationTimeMs);
  return {
    passed: !inner.passed,
    reason: inner.passed
      ? `NOT: condition unexpectedly passed (${inner.reason}).`
      : `NOT: condition failed as expected (${inner.reason}).`,
  };
}

// ---------------------------------------------------------------------------
// Deep equality (no external dependency)
// ---------------------------------------------------------------------------

/** Structural deep equality for JSON-compatible values. */
export function deepEqual(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (typeof a !== typeof b) return false;
  if (a === null || b === null) return a === b;
  if (Array.isArray(a) && Array.isArray(b)) {
    if (a.length !== b.length) return false;
    return a.every((item, i) => deepEqual(item, b[i]));
  }
  if (typeof a === 'object' && typeof b === 'object') {
    const aObj = a as Record<string, unknown>;
    const bObj = b as Record<string, unknown>;
    const aKeys = Object.keys(aObj);
    const bKeys = Object.keys(bObj);
    if (aKeys.length !== bKeys.length) return false;
    return aKeys.every((k) => deepEqual(aObj[k], bObj[k]));
  }
  return false;
}
