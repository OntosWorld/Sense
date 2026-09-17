/**
 * Sense SDK — public API
 *
 * @example TypeScript
 * ```ts
 * import {
 *   SenseMachine,
 *   defineCapability,
 *   gte,
 *   equals,
 *   fresh,
 * } from '@sense/sdk';
 * ```
 *
 * @example JavaScript
 * ```js
 * import { SenseMachine, defineCapability, gte, equals, fresh } from '@sense/sdk';
 * ```
 */

export { SenseMachine } from './sense-machine.js';
export type { SenseMachineConfig } from './sense-machine.js';

// Re-export everything from sense-machine (which re-exports the full public surface)
export type { TelemetryObservation } from './model/observation.js';
export { validateObservation, isStale, observationAgeMs } from './model/observation.js';
export type { NormalizedMachineState } from './model/state.js';
export { applyObservation, getObservation, emptyState } from './model/state.js';
export type { ContextSnapshot, FreshnessSummary, ObservationFreshness } from './model/snapshot.js';
export { buildSnapshot, evaluateFreshness, CONTEXT_SCHEMA_VERSION } from './model/snapshot.js';
export {
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
  gt,
  gte,
  lt,
  lte,
  ALL,
  ANY,
  NOT,
} from './rules/index.js';
export type {
  Rule,
  RuleResult,
  RuleSeverity,
  EqualsRule,
  NotEqualsRule,
  GreaterThanRule,
  GreaterThanOrEqualRule,
  LessThanRule,
  LessThanOrEqualRule,
  ExistsRule,
  InSetRule,
  FreshRule,
  AndRule,
  OrRule,
  NotRule,
  FreshOptions,
} from './rules/index.js';
export { defineCapability } from './engine/capability.js';
export type { CapabilityDefinition } from './engine/capability.js';
export { evaluateCapability } from './engine/evaluator.js';
export type {
  CapabilityStatus,
  UnknownReasonCode,
  CapabilityEvaluationResult,
} from './engine/evaluator.js';
export { TransitionEngine } from './events/index.js';
export type { CapabilityTransition, TransitionCallback } from './events/index.js';
export type { TelemetryAdapter, ObservationSink } from './adapters/index.js';
export { SimulatorAdapter } from './adapters/simulator.js';
export type { SimulatorConfig } from './adapters/simulator.js';
export { PeaqPublisher, hashSnapshot } from './integrations/peaq/index.js';
export type { PeaqConfig, PeaqActivityEvent, PeaqEventPayload } from './integrations/peaq/index.js';
export {
  SenseError,
  SchemaValidationError,
  UnknownCapabilityError,
  MissingEvidenceError,
  InvalidRuleError,
  PeaqConfigurationError,
  PeaqNetworkError,
  UnsupportedPeaqFlowError,
  SerializationError,
  AdapterError,
  StaleEvidenceError,
  InvalidTimestampError,
  InvalidNumericValueError,
} from './errors/index.js';
