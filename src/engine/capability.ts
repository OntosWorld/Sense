/**
 * Sense SDK — capability definitions
 * @module engine/capability
 */

import type { Rule } from '../rules/index.js';

/**
 * A named, evaluated machine capability with typed rules.
 */
export interface CapabilityDefinition {
  /** Unique identifier for this capability. e.g. "warehouse.pick" */
  readonly name: string;

  /**
   * Human-readable description of this capability.
   * Shown in explanations and logs.
   */
  readonly description?: string;

  /**
   * Rules that MUST pass for the capability to be AVAILABLE.
   * Any failure here produces UNAVAILABLE, never AVAILABLE.
   */
  readonly mandatoryRules: readonly Rule[];

  /**
   * Rules that, if they fail, downgrade AVAILABLE to DEGRADED.
   * Failures here never produce UNAVAILABLE.
   */
  readonly degradationRules: readonly Rule[];

  /**
   * Optional tag set for grouping/categorization.
   * e.g. ["warehouse", "logistics"]
   */
  readonly tags?: readonly string[];
}

/**
 * Creates a CapabilityDefinition.
 * All capabilities should be defined through this factory.
 *
 * Supports two call signatures:
 * - defineCapability({ name, mandatoryRules, ... })
 * - defineCapability(name, { requires, degrade?, ... })
 *
 * @example
 * // Object form
 * const pickCapability = defineCapability({
 *   name: 'warehouse.pick',
 *   description: 'Can perform a pick operation in the warehouse.',
 *   mandatoryRules: [equals('tool.gripper.available', true), gte('battery.levelPct', 20)],
 *   degradationRules: [lessThan('battery.levelPct', 50)],
 *   tags: ['warehouse', 'logistics'],
 * });
 *
 * @example
 * // Shorthand form
 * const pickCapability = defineCapability('warehouse.pick', {
 *   requires: [equals('tool.gripper.available', true), gte('battery.levelPct', 20)],
 *   degrade: [lessThan('battery.levelPct', 50)],
 * });
 */
export function defineCapability(
  nameOrConfig:
    | string
    | {
        name?: string;
        description?: string;
        mandatoryRules?: readonly Rule[];
        degradationRules?: readonly Rule[];
        requires?: readonly Rule[];
        degrade?: readonly Rule[];
        tags?: readonly string[];
      },
  rulesConfig?: {
    description?: string;
    mandatoryRules?: readonly Rule[];
    degradationRules?: readonly Rule[];
    requires?: readonly Rule[];
    degrade?: readonly Rule[];
    tags?: readonly string[];
  },
): CapabilityDefinition {
  let name: string;
  let description: string | undefined;
  let mandatoryRules: readonly Rule[];
  let degradationRules: readonly Rule[] | undefined;
  let tags: readonly string[] | undefined;

  if (typeof nameOrConfig === 'string') {
    // Two-argument shorthand form: defineCapability(name, { requires, degrade })
    name = nameOrConfig;
    const config = rulesConfig ?? {};
    mandatoryRules = config.requires ?? config.mandatoryRules ?? [];
    degradationRules = config.degrade ?? config.degradationRules;
    description = config.description;
    tags = config.tags;
  } else {
    // Object form: defineCapability({ name, mandatoryRules, ... })
    name = nameOrConfig.name ?? '';
    mandatoryRules = nameOrConfig.requires ?? nameOrConfig.mandatoryRules ?? [];
    degradationRules = nameOrConfig.degrade ?? nameOrConfig.degradationRules;
    description = nameOrConfig.description;
    tags = nameOrConfig.tags;
  }

  if (!name || name.length === 0) {
    throw new Error('Capability name is required.');
  }
  if (!Array.isArray(mandatoryRules)) {
    throw new Error('mandatoryRules/requires must be an array.');
  }
  return {
    name,
    ...(description !== undefined && { description }),
    mandatoryRules,
    degradationRules: degradationRules ?? [],
    ...(tags !== undefined && { tags }),
  };
}
