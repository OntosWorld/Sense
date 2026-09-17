/**
 * Sense SDK — contract tests: JSON Schema and public API surface
 * @module tests/contract/schema
 */

import { describe, expect, it, beforeAll } from 'vitest';
import Ajv from 'ajv';
import addFormats from 'ajv-formats';
import { readFileSync } from 'fs';
import { resolve } from 'path';
import { SenseMachine, defineCapability, equals, gte, fresh } from '../../src/index.js';
import { SCHEMA_VERSION } from '../../src/schema/versions.js';

function buildTestSnapshot() {
  const machine = new SenseMachine({ machineRef: 'contract-test' });
  machine.observe({ path: 'battery.levelPct', value: 78, observedAt: new Date().toISOString() });
  machine.observe({ path: 'safety.estop', value: false, observedAt: new Date().toISOString() });
  machine.observe({
    path: 'localization.status',
    value: 'localized',
    observedAt: new Date().toISOString(),
  });
  machine.observe({
    path: 'tool.gripper.available',
    value: true,
    observedAt: new Date().toISOString(),
  });
  machine.observe({ path: 'payload.currentKg', value: 8, observedAt: new Date().toISOString() });
  machine.defineCapability(
    defineCapability('warehouse.pick', {
      requires: [
        equals('safety.estop', false),
        gte('battery.levelPct', 20),
        fresh('localization.status', { maxAgeMs: 5000 }),
        equals('tool.gripper.available', true),
      ],
    }),
  );
  machine.evaluate('warehouse.pick');
  return machine.getSnapshot();
}

describe('JSON Schema Draft 2020-12 — context', () => {
  const schemaPath = resolve(import.meta.dirname, '../../schemas/context-1.0.schema.json');
  const schemaText = readFileSync(schemaPath, 'utf-8');
  const schema = JSON.parse(schemaText);

  let ajv: Ajv;
  beforeAll(() => {
    // strictSchema: false needed because our schema uses plain "version" keyword
    // (Draft 2020-12 "version" requires RFC 8949 encoding that Ajv strict mode rejects)
    // validateSchema: false prevents Ajv from trying to resolve the remote
    // $schema URI in the schema JSON (no network access in tests).
    // strictSchema: false allows plain "version" keyword (Draft 2020-12 requires
    // RFC 8949 encoding that Ajv strict mode rejects by default).
    ajv = new Ajv({ allErrors: true, strictSchema: false, validateSchema: false });
    addFormats(ajv);
  });

  it('schema file is valid JSON', () => {
    expect(() => JSON.parse(schemaText)).not.toThrow();
  });

  it('schema uses JSON Schema Draft 2020-12', () => {
    expect(schema.$schema).toBe('https://json-schema.org/draft/2020-12/schema');
  });

  it('schema has correct $id', () => {
    expect(schema.$id).toBe('https://sense-sdk.github.io/schemas/context-1.0.schema.json');
  });

  it('schema validates a minimal valid snapshot', () => {
    const minimal = {
      schemaVersion: '1.0',
      machineRef: 'test-machine',
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {},
    };

    const validate = ajv.compile(schema);
    const valid = validate(minimal);
    expect(valid).toBe(true);
  });

  it('schema validates a full snapshot produced by the SDK', () => {
    const snapshot = buildTestSnapshot();
    const validate = ajv.compile(schema);
    const valid = validate(snapshot);

    if (!valid) {
      console.error('Schema validation errors:', JSON.stringify(validate.errors, null, 2));
    }
    expect(valid).toBe(true);
  });

  it('schema rejects a snapshot without schemaVersion', () => {
    const snapshot = {
      machineRef: 'test-machine',
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {},
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(false);
  });

  it('schema rejects an unknown schema version', () => {
    const snapshot = {
      schemaVersion: '99.0',
      machineRef: 'test-machine',
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {},
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(false);
  });

  it('schema rejects invalid observation timestamp format', () => {
    const snapshot = {
      schemaVersion: '1.0',
      machineRef: 'test-machine',
      timestamp: new Date().toISOString(),
      latestObservationAt: 'not-a-date',
      observations: {
        'battery.levelPct': {
          path: 'battery.levelPct',
          value: 80,
          observedAt: 'not-a-date',
        },
      },
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(false);
  });

  it('schema allows observation value to be any JSON type', () => {
    const snapshot = {
      schemaVersion: '1.0',
      machineRef: 'test-machine',
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {
        counter: { path: 'counter', value: 42, observedAt: new Date().toISOString() },
        flag: { path: 'flag', value: true, observedAt: new Date().toISOString() },
        label: { path: 'label', value: 'hello', observedAt: new Date().toISOString() },
        buffer: { path: 'buffer', value: null, observedAt: new Date().toISOString() },
        point: {
          path: 'point',
          value: { x: 1.5, y: 2.5 },
          observedAt: new Date().toISOString(),
        },
        tags: { path: 'tags', value: ['a', 'b'], observedAt: new Date().toISOString() },
      },
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(true);
  });

  it('schema requires machineRef to be a string', () => {
    const snapshot = {
      schemaVersion: '1.0',
      machineRef: 123,
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {},
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(false);
  });

  it('schema allows optional peaqDid', () => {
    const snapshot = {
      schemaVersion: '1.0',
      machineRef: 'test-machine',
      peaqDid: 'did:peaq:0xabc',
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {},
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(true);
  });

  it('schema allows optional metadata', () => {
    const snapshot = {
      schemaVersion: '1.0',
      machineRef: 'test-machine',
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {},
      metadata: { deploymentId: 'deploy-1', region: 'us-east-1' },
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(true);
  });

  it('schema rejects metadata if it is not an object', () => {
    const snapshot = {
      schemaVersion: '1.0',
      machineRef: 'test-machine',
      timestamp: new Date().toISOString(),
      latestObservationAt: new Date().toISOString(),
      observations: {},
      metadata: 'not-an-object',
    };

    const validate = ajv.compile(schema);
    const valid = validate(snapshot);
    expect(valid).toBe(false);
  });
});

describe('SCHEMA_VERSION constant', () => {
  it('matches the schema JSON file version', () => {
    const schemaPath = resolve(import.meta.dirname, '../../schemas/context-1.0.schema.json');
    const schema = JSON.parse(readFileSync(schemaPath, 'utf-8'));

    expect(SCHEMA_VERSION).toBe('1.0');
    expect(schema.properties?.schemaVersion?.const).toBe('1.0');
  });
});
