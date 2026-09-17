/**
 * Sense SDK — typed error hierarchy
 * @module errors
 */

/**
 * Base error for all Sense SDK errors.
 * Subclasses carry structured context for programmatic handling.
 */
export class SenseError extends Error {
  public readonly code: string;
  public readonly context: Readonly<Record<string, unknown>> | undefined;

  constructor(message: string, code: string, context?: Readonly<Record<string, unknown>>) {
    super(message);
    this.name = this.constructor.name;
    this.code = code;
    this.context = context;
    // Maintains proper stack trace in V8 environments
    Error.captureStackTrace(this, this.constructor);
  }

  override toString(): string {
    const ctx =
      this.context !== undefined
        ? ` [${Object.entries(this.context)
            .map(([k, v]) => `${k}=${JSON.stringify(v)}`)
            .join(', ')}]`
        : '';
    return `${this.name} [${this.code}]: ${this.message}${ctx}`;
  }
}

/** Thrown when an observation or configuration fails JSON Schema validation. */
export class SchemaValidationError extends SenseError {
  constructor(message: string, context?: Readonly<Record<string, unknown>>) {
    super(message, 'SCHEMA_VALIDATION_ERROR', context);
  }
}

/** Thrown when a capability is referenced before being defined. */
export class UnknownCapabilityError extends SenseError {
  constructor(capabilityName: string, context?: Readonly<Record<string, unknown>>) {
    super(`Capability "${capabilityName}" is not defined.`, 'UNKNOWN_CAPABILITY_ERROR', {
      capabilityName,
      ...context,
    });
  }
}

/** Thrown when a required observation is missing during capability evaluation. */
export class MissingEvidenceError extends SenseError {
  constructor(path: string, context?: Readonly<Record<string, unknown>>) {
    super(`Required observation "${path}" is missing.`, 'MISSING_EVIDENCE_ERROR', {
      path,
      ...context,
    });
  }
}

/** Thrown when a rule definition is malformed. */
export class InvalidRuleError extends SenseError {
  constructor(message: string, context?: Readonly<Record<string, unknown>>) {
    super(message, 'INVALID_RULE_ERROR', context);
  }
}

/** Thrown when peaq is configured but the configuration is invalid. */
export class PeaqConfigurationError extends SenseError {
  constructor(message: string, context?: Readonly<Record<string, unknown>>) {
    super(message, 'PEAQ_CONFIGURATION_ERROR', context);
  }
}

/** Thrown when a network call to peaq infrastructure fails. */
export class PeaqNetworkError extends SenseError {
  constructor(message: string, context?: Readonly<Record<string, unknown>>) {
    super(message, 'PEAQ_NETWORK_ERROR', context);
  }
}

/** Thrown when attempting an unsupported peaq operation. */
export class UnsupportedPeaqFlowError extends SenseError {
  constructor(message: string, context?: Readonly<Record<string, unknown>>) {
    super(message, 'UNSUPPORTED_PEAQ_FLOW_ERROR', context);
  }
}

/** Thrown when serialization or deserialization fails. */
export class SerializationError extends SenseError {
  constructor(message: string, context?: Readonly<Record<string, unknown>>) {
    super(message, 'SERIALIZATION_ERROR', context);
  }
}

/** Thrown when a telemetry adapter encounters an error. */
export class AdapterError extends SenseError {
  constructor(message: string, context?: Readonly<Record<string, unknown>>) {
    super(message, 'ADAPTER_ERROR', context);
  }
}

/** Thrown when an observation's age exceeds its configured TTL. */
export class StaleEvidenceError extends SenseError {
  constructor(path: string, ageMs: number, ttlMs: number) {
    super(
      `Observation "${path}" is stale. Age ${ageMs}ms exceeds TTL ${ttlMs}ms.`,
      'STALE_EVIDENCE_ERROR',
      { path, ageMs, ttlMs },
    );
  }
}

/** Thrown when a timestamp is malformed or out of range. */
export class InvalidTimestampError extends SenseError {
  constructor(value: string, reason?: string) {
    super(
      `Invalid timestamp: "${value}".${reason !== undefined ? ` ${reason}` : ''}`,
      'INVALID_TIMESTAMP_ERROR',
      { value, reason },
    );
  }
}

/** Thrown when a numeric observation value is NaN or Infinity. */
export class InvalidNumericValueError extends SenseError {
  constructor(path: string, value: unknown) {
    super(
      `Observation "${path}" has invalid numeric value: ${JSON.stringify(value)}.`,
      'INVALID_NUMERIC_VALUE_ERROR',
      { path, value },
    );
  }
}
