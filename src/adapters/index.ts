/**
 * Sense SDK — telemetry adapter interface
 * @module adapters
 */

import type { TelemetryObservation } from '../model/observation.js';

/**
 * Sink for telemetry observations. Implemented by the SenseMachine.
 */
export interface ObservationSink {
  /**
   * Called by an adapter when it has a new observation.
   * The sink handles validation and state updates.
   */
  accept(observation: TelemetryObservation): void;
}

/**
 * A telemetry adapter translates external data sources into Sense observations.
 *
 * Examples:
 * - ROS 2 topic subscriber
 * - MQTT consumer
 * - HTTP polling client
 * - OEM REST API
 * - Simulator
 *
 * Adapters are started and stopped explicitly by the consumer.
 */
export interface TelemetryAdapter {
  /**
   * Human-readable name for this adapter, used in logs and error messages.
   */
  readonly name: string;

  /**
   * Starts the adapter and begins forwarding observations to the sink.
   * @param sink - The observation sink to forward observations to
   */
  start(sink: ObservationSink): Promise<void>;

  /**
   * Stops the adapter and releases all resources.
   * After stop(), the adapter should not emit further observations.
   */
  stop(): Promise<void>;
}
