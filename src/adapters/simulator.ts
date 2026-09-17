/**
 * Sense SDK — in-process simulator adapter
 * @module adapters/simulator
 *
 * Provides a deterministic machine simulator for development and testing.
 * Not intended for production use.
 */

import type { TelemetryAdapter, ObservationSink } from './index.js';
import type { TelemetryObservation } from '../model/observation.js';
import { AdapterError } from '../errors/index.js';

/**
 * Configuration for the SimulatorAdapter.
 */
export interface SimulatorConfig {
  /**
   * Initial observation values.
   * Key = path, Value = observation value.
   */
  initialValues: Record<string, unknown>;

  /**
   * TTL in ms for each observation. Default: no TTL.
   */
  ttlMs?: number;

  /**
   * Interval in ms between simulation ticks.
   * Default: 1000 (1 second).
   */
  tickIntervalMs?: number;

  /**
   * Optional source identifier for emitted observations.
   * Default: 'simulator'.
   */
  source?: string;

  /**
   * Optional callback to mutate state before each tick.
   * Return a map of path → new value to update observations.
   */
  tickMutator?: (currentValues: Record<string, unknown>) => Record<string, unknown>;
}

/**
 * An in-process simulator that produces telemetry observations at a fixed interval.
 *
 * Useful for:
 * - Development and local testing
 * - Unit and integration tests
 * - Demo environments
 *
 * @example
 * const sim = new SimulatorAdapter({
 *   initialValues: {
 *     'battery.levelPct': 78,
 *     'safety.estop': false,
 *     'localization.status': 'valid',
 *     'tool.gripper.available': true,
 *     'payload.currentKg': 8,
 *     'payload.maxKg': 20,
 *   },
 *   tickIntervalMs: 500,
 * });
 *
 * await machine.useAdapter(sim);
 */
export class SimulatorAdapter implements TelemetryAdapter {
  public readonly name = 'SimulatorAdapter';
  private _sink: ObservationSink | undefined;
  private _timer: ReturnType<typeof setInterval> | undefined;
  private _running = false;
  private _currentValues: Record<string, unknown>;
  private _tickIntervalMs: number;
  private _ttlMs: number | undefined;
  private _source: string;
  private _tickMutator:
    ((currentValues: Record<string, unknown>) => Record<string, unknown>) | undefined;

  constructor(config: SimulatorConfig) {
    if (!config.initialValues || typeof config.initialValues !== 'object') {
      throw new AdapterError('SimulatorConfig.initialValues is required.', {});
    }
    this._currentValues = { ...config.initialValues };
    this._tickIntervalMs = config.tickIntervalMs ?? 1000;
    this._ttlMs = config.ttlMs;
    this._source = config.source ?? 'simulator';
    this._tickMutator = config.tickMutator;
  }

  async start(sink: ObservationSink): Promise<void> {
    if (this._running) return;
    this._sink = sink;
    this._running = true;

    // Emit initial state immediately
    await this._emitAll();

    // Then emit on interval
    this._timer = setInterval(async () => {
      await this._tick();
    }, this._tickIntervalMs);
  }

  async stop(): Promise<void> {
    if (!this._running) return;
    this._running = false;
    if (this._timer !== undefined) {
      clearInterval(this._timer);
      this._timer = undefined;
    }
    this._sink = undefined;
  }

  /** Updates a single value in the simulator (useful for testing). */
  setValue(path: string, value: unknown): void {
    this._currentValues[path] = value;
  }

  /** Returns a copy of current simulation values. */
  getValues(): Record<string, unknown> {
    return { ...this._currentValues };
  }

  /** Injects a custom observation (bypasses the tick loop). */
  inject(observation: TelemetryObservation): void {
    this._sink?.accept(observation);
  }

  private async _tick(): Promise<void> {
    if (!this._running || this._sink === undefined) return;

    // Apply mutator if provided
    if (this._tickMutator) {
      try {
        const updated = this._tickMutator(this._currentValues);
        if (updated && typeof updated === 'object') {
          this._currentValues = { ...updated };
        }
      } catch (err) {
        throw new AdapterError(
          `SimulatorAdapter tickMutator threw: ${err instanceof Error ? err.message : String(err)}`,
          { name: this.name },
        );
      }
    }

    await this._emitAll();
  }

  private async _emitAll(): Promise<void> {
    if (this._sink === undefined) return;
    const now = new Date().toISOString();

    for (const [path, value] of Object.entries(this._currentValues)) {
      const obs: TelemetryObservation = {
        path,
        value,
        observedAt: now,
        source: this._source,
        ...(this._ttlMs !== undefined && { ttlMs: this._ttlMs }),
      };
      this._sink.accept(obs);
    }
  }
}
