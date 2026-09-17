/**
 * Sense SDK — engine barrel export
 * @module engine
 */

export { defineCapability } from './capability.js';
export type { CapabilityDefinition } from './capability.js';

export { evaluateCapability } from './evaluator.js';
export type {
  CapabilityStatus,
  UnknownReasonCode,
  CapabilityEvaluationResult,
} from './evaluator.js';
