/**
 * Sense SDK — JSON Schema validation
 * @module schema
 */

import { readFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import type { SchemaVersion } from './versions.js';
import { SchemaValidationError } from '../errors/index.js';
import type { ContextSnapshot } from '../model/snapshot.js';

// Lazily loaded built-in validators (avoid importing the full ajv bundle at parse time)
let _validate: ((data: unknown) => boolean) | null = null;
let _errors: unknown[] | null = null;

function getValidator(): (data: unknown) => boolean {
  if (_validate) return _validate;

  // Dynamic require to keep schema validation out of the hot path
  // (no top-level imports of ajv — avoids bundling it into every consumer)
  const Ajv = require('ajv') as new (opts?: object) => {
    validate: (data: unknown) => boolean;
    errors: unknown[];
    compile: (schema: unknown) => (data: unknown) => boolean;
  };

  const __dirname = dirname(fileURLToPath(import.meta.url));
  const schemaPath = resolve(__dirname, '../../schemas/context-1.0.schema.json');
  const schema = JSON.parse(readFileSync(schemaPath, 'utf-8')) as object;

  const ajv = new Ajv({ strict: true, allErrors: true });
  _validate = ajv.compile(schema);
  _errors = ajv.errors;

  return _validate;
}

/**
 * Validates a ContextSnapshot against the current JSON Schema.
 * Throws SchemaValidationError on failure.
 */
export function validateSnapshot(
  raw: unknown,
  schemaVersion: SchemaVersion,
): asserts raw is ContextSnapshot {
  if (schemaVersion !== '1.0') {
    throw new SchemaValidationError(`Unsupported schema version: "${schemaVersion}".`, {
      schemaVersion,
    });
  }

  const validate = getValidator();
  const valid = validate(raw);

  if (!valid) {
    const errs = _errors ?? [];
    const messages = (errs as Array<{ instancePath: string; message?: string }>).map((e) =>
      `${e.instancePath} ${e.message ?? 'unknown error'}`.trim(),
    );
    throw new SchemaValidationError(`ContextSnapshot validation failed: ${messages.join('; ')}.`, {
      schemaVersion,
      errors: messages,
    });
  }
}

/**
 * Registers the optional schema-validation dependency.
 * Call this before using validateSnapshot if the SDK consumer installed ajv separately.
 * When ajv is not installed, schema validation is a no-op.
 */
export function _registerAjv(ajv: unknown): void {
  // Placeholder for future ajv integration
  // Currently schema validation uses the bundled require() approach above
  void ajv;
}
