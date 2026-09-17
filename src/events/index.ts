/**
 * Sense SDK — transition engine
 * @module events
 */

import type { CapabilityStatus } from '../engine/index.js';
import type { CapabilityEvaluationResult } from '../engine/evaluator.js';

/**
 * A detected change in capability status.
 */
export interface CapabilityTransition {
  /** Name of the capability that changed. */
  readonly capability: string;

  /** Status before the change. undefined if previously unknown/unevaluated. */
  readonly previousStatus: CapabilityStatus | undefined;

  /** Current status after the change. */
  readonly currentStatus: CapabilityStatus;

  /** ISO 8601 timestamp when the transition was detected. */
  readonly timestamp: string;

  /**
   * Human-readable explanation of what changed and why.
   */
  readonly explanation: string;

  /**
   * Paths whose values contributed to this transition.
   */
  readonly changedPaths: readonly string[];

  /**
   * Optional structured reason code for machine-readable consumption.
   */
  readonly reasonCode?: string;

  /** Convenience alias for previousStatus (for display/testing). */
  readonly from?: CapabilityStatus;

  /** Convenience alias for currentStatus (for display/testing). */
  readonly to?: CapabilityStatus;
}

/**
 * Callback type for transition subscriptions.
 */
export type TransitionCallback = (transition: CapabilityTransition) => void | Promise<void>;

/**
 * Internal record for tracking previous evaluation results.
 */
interface TransitionTracker {
  previousResult: CapabilityEvaluationResult | undefined;
}

/**
 * Manages capability evaluation state and emits transitions.
 * Use one TransitionEngine per SenseMachine.
 */
export class TransitionEngine {
  private readonly _trackers = new Map<string, TransitionTracker>();
  private readonly _subscribers = new Map<string, Set<TransitionCallback>>();

  /**
   * Evaluates a capability and emits a transition if the status changed.
   * Returns the evaluation result and whether a transition occurred.
   */
  evaluateAndEmit(result: CapabilityEvaluationResult): {
    result: CapabilityEvaluationResult;
    transitioned: boolean;
    transition?: CapabilityTransition;
  } {
    const tracker = this._trackers.get(result.name) ?? { previousResult: undefined };
    const prev = tracker.previousResult;
    this._trackers.set(result.name, tracker);

    // No transition if the status is the same (unless previous was undefined)
    if (prev !== undefined && prev.status === result.status) {
      // Check if any failed paths changed — if so, still worth noting
      const prevFailed = new Set(prev.failedPaths);
      const currFailed = new Set(result.failedPaths);
      const changedPaths = [...currFailed].filter((p) => !prevFailed.has(p));

      // Still a transition if the explanation meaningfully changed for UNKNOWN
      if (result.status === 'UNKNOWN' && prev.unknownReason !== result.unknownReason) {
        const transition = this._buildTransition(result, prev.status, changedPaths);
        this._emit(result.name, transition);
        tracker.previousResult = result;
        return { result, transitioned: true, transition };
      }

      // No meaningful transition
      return { result, transitioned: false };
    }

    const changedPaths =
      prev !== undefined
        ? [...new Set([...prev.failedPaths, ...result.failedPaths])]
        : result.failedPaths;

    const transition = this._buildTransition(result, prev?.status, changedPaths);
    this._emit(result.name, transition);
    tracker.previousResult = result;

    return { result, transitioned: true, transition };
  }

  /**
   * Subscribes to transitions for a specific capability.
   * @param capabilityName - '*' subscribes to all transitions
   */
  onTransition(capabilityName: string, callback: TransitionCallback): () => void {
    if (!this._subscribers.has(capabilityName)) {
      this._subscribers.set(capabilityName, new Set());
    }
    this._subscribers.get(capabilityName)!.add(callback);

    // Return an unsubscribe function
    return () => {
      this._subscribers.get(capabilityName)?.delete(callback);
    };
  }

  /**
   * Returns the previous evaluation result for a capability, if any.
   */
  getPreviousResult(name: string): CapabilityEvaluationResult | undefined {
    return this._trackers.get(name)?.previousResult;
  }

  /**
   * Resets transition tracking for a specific capability.
   * Useful after a machine reconfiguration.
   */
  reset(capabilityName?: string): void {
    if (capabilityName !== undefined) {
      this._trackers.delete(capabilityName);
    } else {
      this._trackers.clear();
    }
  }

  /**
   * Records a transition directly (for testing and manual use).
   * Silently skips if `from` equals `to` or both are 'UNKNOWN'.
   */
  recordTransition(
    capability: string,
    from: CapabilityStatus,
    to: CapabilityStatus,
    explanation = `${capability} changed`,
  ): void {
    // Skip no-op transitions
    if (from === to) return;
    if (from === 'UNKNOWN' && to === 'UNKNOWN') return;

    const transition: CapabilityTransition = Object.freeze({
      capability,
      previousStatus: from,
      currentStatus: to,
      timestamp: new Date().toISOString(),
      explanation,
      changedPaths: [],
      from,
      to,
    });

    this._emit(capability, transition);
  }

  private _buildTransition(
    result: CapabilityEvaluationResult,
    previousStatus: CapabilityStatus | undefined,
    changedPaths: readonly string[],
  ): CapabilityTransition {
    const reasonCode = result.unknownReason ?? result.unavailableReason;
    return {
      capability: result.name,
      previousStatus,
      currentStatus: result.status,
      timestamp: result.evaluatedAt,
      explanation: result.explanation,
      changedPaths,
      ...(reasonCode !== undefined && { reasonCode }),
    };
  }

  private _emit(capabilityName: string, transition: CapabilityTransition): void {
    // Freeze the transition before emitting so subscribers cannot mutate it
    const frozen = Object.freeze({ ...transition });

    // Emit to specific subscribers
    this._subscribers.get(capabilityName)?.forEach((cb) => {
      try {
        void cb(frozen);
      } catch {
        // Swallow subscriber errors to protect the engine
      }
    });
    // Emit to wildcard subscribers
    this._subscribers.get('*')?.forEach((cb) => {
      try {
        void cb(frozen);
      } catch {
        // Swallow subscriber errors
      }
    });
  }
}
