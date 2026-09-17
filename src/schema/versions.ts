/**
 * Sense SDK — schema version type
 * @module schema/versions
 */

/**
 * All supported context schema versions.
 * Package version and schema version are independent.
 */
export type SchemaVersion = '1.0';

/** Current schema version used by the SDK. */
export const CURRENT_SCHEMA_VERSION: SchemaVersion = '1.0';

/** Alias so consumers can import SCHEMA_VERSION directly from the schema module. */
export { CURRENT_SCHEMA_VERSION as SCHEMA_VERSION };
