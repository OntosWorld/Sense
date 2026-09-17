/**
 * Sense SDK — peaq integration
 * @module integrations/peaq
 *
 * Connects Sense context transitions to peaq activity events.
 *
 * IMPORTANT: This module implements against peaq's documented API surface.
 * Verify each operation against https://docs.peaq.xyz/ before relying on it.
 *
 * BLOCKED / NEEDS CONFIRMATION:
 * TODO(peaq-confirmation): Verify the exact activity event schema (field names, types, limits).
 * TODO(peaq-confirmation): Confirm whether events are published via SDK call or REST.
 * TODO(peaq-confirmation): Confirm the peaq DID format and validation rules.
 * TODO(peaq-confirmation): Verify the event metadata size limits.
 */

import type { CapabilityTransition } from '../../events/index.js';
import type { ContextSnapshot } from '../../model/snapshot.js';
import {
  PeaqConfigurationError,
  PeaqNetworkError,
  UnsupportedPeaqFlowError,
} from '../../errors/index.js';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/**
 * Configuration for the peaq integration.
 * All fields are validated before use.
 */
export interface PeaqConfig {
  /**
   * The peaq DID of this machine.
   * Format: "did:peaq:<hex-or-base58-identifier>"
   */
  readonly did: string;

  /**
   * The peaq network to target.
   * @default 'testnet'
   */
  readonly network?: 'testnet' | 'mainnet';

  /**
   * Optional peaq SDK instance for direct SDK integration.
   * When absent, uses HTTP API calls.
   *
   * TODO(peaq-confirmation): Confirm the SDK type for activity event publishing.
   */
  readonly sdk?: unknown;

  /**
   * Optional REST API endpoint override.
   * Defaults to the official peaq network endpoint.
   */
  readonly apiEndpoint?: string;

  /**
   * Optional API key for authenticated endpoints.
   * Never log this value.
   */
  readonly apiKey?: string;
}

// ---------------------------------------------------------------------------
// Activity event types
// ---------------------------------------------------------------------------

/**
 * The Sense-specific activity event type on peaq.
 * Maps a capability transition to a peaq-compatible activity event.
 *
 * TODO(peaq-confirmation): Verify the exact field names and limits from peaq docs.
 */
export interface PeaqActivityEvent {
  /** peaq DID of the machine. */
  readonly did: string;

  /**
   * Event type identifier.
   * Sense uses "capability.transition" for all capability state changes.
   */
  readonly type: string;

  /**
   * ISO 8601 timestamp of the transition.
   */
  readonly timestamp: string;

  /**
   * Human-readable description of the event.
   * Subject to peaq metadata size limits.
   */
  readonly description: string;

  /**
   * Machine-readable payload with structured transition data.
   * Serialized as JSON and included in the event.
   */
  readonly payload: PeaqEventPayload;

  /**
   * Optional SHA-256 hash of the context snapshot at transition time.
   * Provides tamper-evidence for the snapshot that triggered the transition.
   *
   * TODO(peaq-confirmation): Confirm peaq supports attaching a hash to events.
   */
  readonly snapshotHash?: string;
}

export interface PeaqEventPayload {
  /** Capability name, e.g. "warehouse.pick" */
  readonly capability: string;

  /** Previous status, undefined if previously unknown. */
  readonly previousStatus: string | undefined;

  /** Current status after the transition. */
  readonly currentStatus: string;

  /** ISO 8601 timestamp. */
  readonly timestamp: string;

  /** Reason code from the evaluation engine. */
  readonly reasonCode?: string;

  /** Paths that contributed to the transition. */
  readonly changedPaths: readonly string[];

  /** Machine reference from the snapshot. */
  readonly machineRef: string;

  /** Context schema version. */
  readonly schemaVersion: string;
}

// ---------------------------------------------------------------------------
// PeaqPublisher
// ---------------------------------------------------------------------------

/**
 * Publishes selected Sense capability transitions as peaq activity events.
 *
 * Publishing is always opt-in. Raw telemetry is never uploaded automatically.
 *
 * @example
 * const publisher = new PeaqPublisher({
 *   did: 'did:peaq:0x...',
 *   network: 'testnet',
 * });
 *
 * await publisher.publishTransition(transition, snapshot);
 */
export class PeaqPublisher {
  private readonly _config: Readonly<PeaqConfig>;

  constructor(config: PeaqConfig) {
    this._config = {
      did: config.did,
      network: config.network ?? 'testnet',
      sdk: config.sdk,
      ...(config.apiEndpoint !== undefined && { apiEndpoint: config.apiEndpoint }),
      ...(config.apiKey !== undefined && { apiKey: config.apiKey }),
    };

    this._validateConfig();
  }

  /** Returns the peaq DID associated with this publisher. */
  get did(): string {
    return this._config.did;
  }

  /** Returns the target network. */
  get network(): 'testnet' | 'mainnet' {
    return this._config.network as 'testnet' | 'mainnet';
  }

  /**
   * Publishes a capability transition as a peaq activity event.
   *
   * @param transition - The capability transition to publish
   * @param snapshot - The context snapshot at transition time (for hash)
   * @returns The published event with any server-assigned fields
   * @throws PeaqConfigurationError if configuration is invalid
   * @throws PeaqNetworkError if the publish call fails
   * @throws UnsupportedPeaqFlowError if the peaq SDK doesn't support this operation
   */
  async publishTransition(
    transition: CapabilityTransition,
    snapshot?: ContextSnapshot,
  ): Promise<PeaqActivityEvent> {
    const snapshotHash = snapshot ? await this._hashSnapshot(snapshot) : undefined;

    const event: PeaqActivityEvent = {
      did: this._config.did,
      type: 'capability.transition',
      timestamp: transition.timestamp,
      description: `${transition.capability}: ${transition.previousStatus ?? '?'} → ${transition.currentStatus}. ${transition.explanation}`,
      payload: {
        capability: transition.capability,
        previousStatus: transition.previousStatus,
        currentStatus: transition.currentStatus,
        timestamp: transition.timestamp,
        ...(transition.reasonCode !== undefined && { reasonCode: transition.reasonCode }),
        changedPaths: transition.changedPaths,
        machineRef: snapshot?.machineRef ?? '',
        schemaVersion: snapshot?.schemaVersion ?? '1.0',
      },
      ...(snapshotHash !== undefined && { snapshotHash }),
    };

    return this._publishEvent(event);
  }

  /**
   * Validates that the peaq DID format is acceptable.
   *
   * TODO(peaq-confirmation): Confirm the exact DID format and regex from peaq docs.
   */
  private _validateDID(did: string): void {
    const PEAQ_DID_REGEX = /^did:peaq:[A-Za-z0-9]+$/;
    if (!PEAQ_DID_REGEX.test(did)) {
      throw new PeaqConfigurationError(
        `Invalid peaq DID format: "${did}". Expected format: did:peaq:<identifier>`,
        { did },
      );
    }
  }

  private _validateConfig(): void {
    if (!this._config.did || this._config.did.length === 0) {
      throw new PeaqConfigurationError('peaq DID is required.', {});
    }
    this._validateDID(this._config.did);
  }

  private async _publishEvent(event: PeaqActivityEvent): Promise<PeaqActivityEvent> {
    // Use SDK if provided, otherwise HTTP
    if (this._config.sdk !== undefined) {
      return this._publishViaSdk(event);
    }
    return this._publishViaHttp(event);
  }

  /**
   * Publishes via the peaq SDK, if one is provided.
   *
   * TODO(peaq-confirmation): Verify the exact peaq SDK method for activity events.
   * BLOCKED: Official peaq JS/TS SDK method signature not confirmed.
   */
  private async _publishViaSdk(_event: PeaqActivityEvent): Promise<PeaqActivityEvent> {
    // TODO(peaq-confirmation): Replace with actual SDK call once verified.
    // Expected concept (not confirmed):
    //
    // const sdk = this._config.sdk as PeaqSDK;
    // const txHash = await sdk.activity.publish({
    //   did: event.did,
    //   type: event.type,
    //   description: event.description,
    //   metadata: JSON.stringify(event.payload),
    // });
    //
    throw new UnsupportedPeaqFlowError(
      'peaq SDK-based publishing is not yet implemented. ' +
        'Provide an apiEndpoint to use HTTP-based publishing, or verify the SDK API.',
      { did: this._config.did },
    );
  }

  /**
   * Publishes via the peaq REST API.
   *
   * TODO(peaq-confirmation): Verify the exact REST endpoint and auth method.
   * BLOCKED: Official peaq REST API endpoint for activity events not confirmed.
   */
  private async _publishViaHttp(event: PeaqActivityEvent): Promise<PeaqActivityEvent> {
    const endpoint =
      this._config.apiEndpoint ??
      (this._config.network === 'mainnet'
        ? 'https://api.peaq.xyz/v1/activity'
        : 'https://api.test.peaq.xyz/v1/activity');

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (this._config.apiKey) {
      headers['Authorization'] = `Bearer ${this._config.apiKey}`;
    }

    let response: Response;
    try {
      response = await fetch(endpoint, {
        method: 'POST',
        headers,
        body: JSON.stringify(event),
        signal: AbortSignal.timeout(10_000),
      });
    } catch (err) {
      throw new PeaqNetworkError(
        `Failed to reach peaq API at ${endpoint}: ${err instanceof Error ? err.message : String(err)}`,
        { endpoint, did: this._config.did },
      );
    }

    if (!response.ok) {
      let detail = '';
      try {
        const body = await response.json();
        detail = (body as { message?: string }).message ?? detail;
      } catch {
        detail = `HTTP ${response.status}`;
      }
      throw new PeaqNetworkError(`peaq activity event publish failed: ${detail}`, {
        endpoint,
        status: response.status,
        did: this._config.did,
      });
    }

    return event;
  }

  /**
   * Computes a SHA-256 hash of the snapshot for tamper-evidence.
   * Exposed so consumers can verify the hash independently.
   */
  private async _hashSnapshot(snapshot: ContextSnapshot): Promise<string> {
    const canonical = JSON.stringify(snapshot, Object.keys(snapshot).sort());
    const encoder = new TextEncoder();
    const data = encoder.encode(canonical);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  }
}

// ---------------------------------------------------------------------------
// Utility: hash a context snapshot
// ---------------------------------------------------------------------------

/**
 * Computes a SHA-256 hash of a ContextSnapshot.
 * Useful for tamper-evidence and audit trails.
 */
export async function hashSnapshot(snapshot: ContextSnapshot): Promise<string> {
  const canonical = JSON.stringify(snapshot, Object.keys(snapshot).sort());
  const encoder = new TextEncoder();
  const data = encoder.encode(canonical);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}
