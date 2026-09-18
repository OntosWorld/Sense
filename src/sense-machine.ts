/**
 * Sense SDK — main machine interface
 * @module sense-machine
 */

import type { TelemetryObservation } from './model/observation.js';
import { validateObservation } from './model/observation.js';
import { applyObservation, emptyState } from './model/state.js';
import type { NormalizedMachineState } from './model/state.js';
import { buildSnapshot } from './model/snapshot.js';
import type { ContextSnapshot } from './model/snapshot.js';
import { TransitionEngine } from './events/index.js';
import type { CapabilityTransition, TransitionCallback } from './events/index.js';
import { evaluateCapability } from './engine/evaluator.js';
import type {
  CapabilityDefinition,
  CapabilityEvaluationResult,
  CapabilityStatus,
} from './engine/index.js';
import type { TelemetryAdapter, ObservationSink } from './adapters/index.js';
import { PeaqPublisher } from './integrations/peaq/index.js';
import type { PeaqConfig } from './integrations/peaq/index.js';

// ---------------------------------------------------------------------------
// SenseMachine configuration
// ---------------------------------------------------------------------------

export interface SenseMachineConfig {
  /**
   * Developer-assigned machine reference.
   * Used in snapshots and for transition identification.
   */
  readonly machineRef: string;

  /**
   * Optional peaq DID. If provided, enables peaq integration.
   */
  readonly peaqDid?: string;

  /**
   * Optional peaq network configuration.
   */
  readonly peaqConfig?: Omit<PeaqConfig, 'did'>;

  /**
   * If true, peaq publishing failures are logged but do not throw.
   * @default false
   */
  readonly peaqFailSilently?: boolean;
}

// ---------------------------------------------------------------------------
// SenseMachine
// ---------------------------------------------------------------------------

/**
 * The primary developer-facing class for the Sense SDK.
 *
 * Represents one physical machine or simulated machine with a set of
 * telemetry observations, defined capabilities, and optional peaq integration.
 *
 * All state is kept in-memory. For persistence, use a custom adapter or store.
 *
 * @example TypeScript
 * ```ts
 * import { SenseMachine, defineCapability, gte, equals, fresh } from '@sense/sdk';
 *
 * const machine = new SenseMachine({ machineRef: 'robot-001' });
 *
 * machine.defineCapability(defineCapability({
 *   name: 'warehouse.pick',
 *   mandatoryRules: [
 *     equals('tool.gripper.available', true),
 *     equals('safety.estop', false),
 *     gte('battery.levelPct', 20),
 *     fresh('localization.pose', { maxAgeMs: 1000 }),
 *   ],
 *   degradationRules: [gte('battery.levelPct', 50)],
 * }));
 *
 * machine.observe({ path: 'battery.levelPct', value: 78, observedAt: new Date() });
 *
 * const result = machine.evaluate('warehouse.pick');
 * console.log(result.status); // AVAILABLE
 * ```
 *
 * @example JavaScript
 * ```js
 * import { SenseMachine } from '@sense/sdk';
 * const machine = new SenseMachine({ machineRef: 'robot-001' });
 * machine.observe({ path: 'battery.levelPct', value: 78, observedAt: new Date().toISOString() });
 * const result = machine.evaluate('warehouse.pick');
 * console.log(result.status);
 * ```
 */
export class SenseMachine implements ObservationSink {
  /** Developer-assigned machine reference. */
  public readonly machineRef: string;

  /** peaq DID if configured. */
  public readonly peaqDid: string | undefined;

  private _state: NormalizedMachineState;
  private readonly _capabilities = new Map<string, CapabilityDefinition>();
  private readonly _transitionEngine: TransitionEngine;
  private _adapter: TelemetryAdapter | undefined;
  private _peaqPublisher: PeaqPublisher | undefined;
  private readonly _peaqFailSilently: boolean;
  private _started = false;

  constructor(config: SenseMachineConfig) {
    if (!config.machineRef || config.machineRef.length === 0) {
      throw new Error('machineRef is required.');
    }
    this.machineRef = config.machineRef;
    this.peaqDid = config.peaqDid;
    this._state = emptyState();
    this._transitionEngine = new TransitionEngine();
    this._peaqFailSilently = config.peaqFailSilently ?? false;

    if (config.peaqDid) {
      this._peaqPublisher = new PeaqPublisher({
        did: config.peaqDid,
        ...config.peaqConfig,
      });
    }
  }

  // -------------------------------------------------------------------------
  // Observation API
  // -------------------------------------------------------------------------

  /**
   * Ingests a telemetry observation.
   * The observation is validated and merged into machine state.
   *
   * @param observation - The observation to ingest
   * @throws {InvalidTimestampError} if observedAt is not a valid ISO 8601 string
   * @throws {InvalidNumericValueError} if ttlMs is invalid
   */
  observe(observation: TelemetryObservation): this {
    const validated = validateObservation(observation);
    this._state = applyObservation(this._state, validated);
    return this;
  }

  /**
   * Ingests multiple telemetry observations at once.
   *
   * @param observations - Array of observations to ingest
   */
  observeMany(observations: readonly TelemetryObservation[]): void {
    for (const obs of observations) {
      this.observe(obs);
    }
  }

  /**
   * Returns the current machine state snapshot.
   */
  getState(): NormalizedMachineState {
    return this._state;
  }

  /**
   * Returns the observation for a specific path, or undefined.
   */
  getObservation(path: string): TelemetryObservation | undefined {
    return this._state.observations.get(path);
  }

  /**
   * @internal
   * Implements ObservationSink so adapters can push observations in.
   */
  accept(observation: TelemetryObservation): void {
    this.observe(observation);
  }

  // -------------------------------------------------------------------------
  // Capability API
  // -------------------------------------------------------------------------

  /**
   * Defines a new capability for this machine.
   *
   * @param definition - The capability definition (from defineCapability)
   * @throws Error if a capability with the same name is already defined
   */
  defineCapability(definition: CapabilityDefinition): void {
    if (this._capabilities.has(definition.name)) {
      throw new Error(`Capability "${definition.name}" is already defined.`);
    }
    this._capabilities.set(definition.name, definition);
  }

  /**
   * Returns all defined capability names.
   */
  listCapabilities(): readonly string[] {
    return [...this._capabilities.keys()];
  }

  /**
   * Evaluates a single capability.
   * Detects and emits a transition if the status changed.
   *
   * @param capabilityName - Name of the capability to evaluate
   * @returns The evaluation result, or undefined if the capability is not registered
   */
  evaluate(capabilityName: string): CapabilityEvaluationResult | undefined {
    const capability = this._capabilities.get(capabilityName);
    if (capability === undefined) {
      return undefined;
    }
    const result = evaluateCapability(capability, this._state, Date.now());
    this._transitionEngine.evaluateAndEmit(result);
    return result;
  }

  /**
   * Evaluates all defined capabilities.
   *
   * @returns Map of capability name → evaluation result
   */
  evaluateAll(): Map<string, CapabilityEvaluationResult> {
    const results = new Map<string, CapabilityEvaluationResult>();
    for (const [name, capability] of this._capabilities) {
      const result = evaluateCapability(capability, this._state, Date.now());
      this._transitionEngine.evaluateAndEmit(result);
      results.set(name, result);
    }
    return results;
  }

  /**
   * Returns the current status for a capability without re-evaluating.
   * Returns undefined if the capability has never been evaluated.
   */
  getStatus(capabilityName: string): CapabilityStatus | undefined {
    return this._transitionEngine.getPreviousResult(capabilityName)?.status;
  }

  // -------------------------------------------------------------------------
  // Transition API
  // -------------------------------------------------------------------------

  /**
   * Subscribes to capability transitions.
   *
   * @param capabilityName - Capability to watch, or '*' for all
   * @param callback - Called with the transition when it occurs
   * @returns Unsubscribe function
   *
   * @example
   * const unsub = machine.onTransition('warehouse.pick', (t) => {
   *   console.log(`${t.capability}: ${t.previousStatus} → ${t.currentStatus}`);
   * });
   * // Later:
   * unsub();
   */
  onTransition(capabilityName: string, callback: TransitionCallback): () => void {
    return this._transitionEngine.onTransition(capabilityName, callback);
  }

  /**
   * Returns the most recent transition for a capability.
   */
  getLastTransition(capabilityName: string): CapabilityTransition | undefined {
    const prev = this._transitionEngine.getPreviousResult(capabilityName);
    if (!prev) return undefined;
    return {
      capability: prev.name,
      previousStatus: prev?.status,
      currentStatus: prev.status,
      timestamp: prev.evaluatedAt,
      explanation: prev.explanation,
      changedPaths: prev.failedPaths,
      ...(prev.unknownReason !== undefined && { reasonCode: prev.unknownReason }),
      ...(prev.unavailableReason !== undefined && { reasonCode: prev.unavailableReason }),
    };
  }

  // -------------------------------------------------------------------------
  // Adapter API
  // -------------------------------------------------------------------------

  /**
   * Connects a telemetry adapter to this machine.
   * Replaces any previously connected adapter.
   *
   * @param adapter - The adapter to connect
   * @throws Error if an adapter is already running
   */
  async useAdapter(adapter: TelemetryAdapter): Promise<void> {
    if (this._started) {
      throw new Error('An adapter is already running. Stop it first.');
    }
    this._adapter = adapter;
    await adapter.start(this);
    this._started = true;
  }

  /**
   * Stops the currently connected adapter.
   */
  async stopAdapter(): Promise<void> {
    if (this._adapter && this._started) {
      await this._adapter.stop();
      this._started = false;
    }
  }

  // -------------------------------------------------------------------------
  // peaq integration
  // -------------------------------------------------------------------------

  /**
   * Publishes the current capability transition to peaq.
   * Requires peaq to be configured at construction time.
   *
   * @param capabilityName - The capability whose transition to publish
   * @param redactPaths - Optional paths to exclude from the snapshot
   * @throws Error if peaq is not configured
   */
  async publishTransition(capabilityName: string, redactPaths?: readonly string[]): Promise<void> {
    if (!this._peaqPublisher) {
      throw new Error('peaq is not configured. Provide peaqDid in the constructor.');
    }

    const prev = this._transitionEngine.getPreviousResult(capabilityName);
    if (!prev) {
      throw new Error(`Capability "${capabilityName}" has not been evaluated yet.`);
    }

    const snapshot = buildSnapshot(this._state, this.machineRef, this.peaqDid, redactPaths);

    // Build a synthetic transition for publishing
    const transition: CapabilityTransition = {
      capability: prev.name,
      previousStatus: prev?.status,
      currentStatus: prev.status,
      timestamp: prev.evaluatedAt,
      explanation: prev.explanation,
      changedPaths: prev.failedPaths,
      ...(prev.unknownReason !== undefined && { reasonCode: prev.unknownReason }),
      ...(prev.unavailableReason !== undefined && { reasonCode: prev.unavailableReason }),
    };

    try {
      await this._peaqPublisher.publishTransition(transition, snapshot);
    } catch (err) {
      if (!this._peaqFailSilently) {
        throw err;
      }
      // Log and continue
      console.error('[Sense/peaq] publishTransition failed:', err);
    }
  }

  // -------------------------------------------------------------------------
  // Snapshot / serialization
  // -------------------------------------------------------------------------

  /**
   * Produces a publishable context snapshot.
   *
   * @param redactPaths - Paths to exclude from the snapshot (privacy denylist)
   * @param metadata - Optional additional metadata
   * @param allowPaths - Optional allowlist: if set, only these paths are included (denylist is applied on top)
   */
  getSnapshot(
    redactPaths?: readonly string[],
    metadata?: Record<string, unknown>,
    allowPaths?: readonly string[],
  ): ContextSnapshot {
    return buildSnapshot(
      this._state,
      this.machineRef,
      this.peaqDid,
      redactPaths,
      metadata,
      allowPaths,
    );
  }

  /**
   * Resets the machine state and all transition tracking.
   * Useful for testing or machine reconfiguration.
   */
  reset(): void {
    this._state = emptyState();
    this._transitionEngine.reset();
  }
}

// Re-export everything public from the SDK
export {
  // model
  type TelemetryObservation,
  validateObservation,
  isStale,
  observationAgeMs,
} from './model/observation.js';

export type { NormalizedMachineState } from './model/state.js';
export { applyObservation, getObservation, emptyState } from './model/state.js';

export type { ContextSnapshot, FreshnessSummary, ObservationFreshness } from './model/snapshot.js';
export { buildSnapshot, evaluateFreshness, CONTEXT_SCHEMA_VERSION } from './model/snapshot.js';

// rules
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
  // aliases
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

// engine
export { defineCapability } from './engine/capability.js';
export type { CapabilityDefinition } from './engine/capability.js';
export { evaluateCapability } from './engine/evaluator.js';
export type {
  CapabilityStatus,
  UnknownReasonCode,
  CapabilityEvaluationResult,
} from './engine/evaluator.js';

// events
export { TransitionEngine } from './events/index.js';
export type { CapabilityTransition, TransitionCallback } from './events/index.js';

// adapters
export type { TelemetryAdapter, ObservationSink } from './adapters/index.js';
export { SimulatorAdapter } from './adapters/simulator.js';
export type { SimulatorConfig } from './adapters/simulator.js';

// peaq
export { PeaqPublisher, hashSnapshot } from './integrations/peaq/index.js';
export type { PeaqConfig, PeaqActivityEvent, PeaqEventPayload } from './integrations/peaq/index.js';

// errors
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
