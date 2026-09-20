# Compatibility Policy

Sense is currently pre-1.0.

## Python

Sense 0.3.x supports Python 3.10, 3.11, and 3.12.

CI runs the core unit suite on all three versions.

## Package versions

The repository keeps the first-party packages aligned:

```text
sense-ai
sense-peaq
sense-ros2
sense-mqtt
sense-http
```

For the planned 0.3 release line, all first-party packages use version `0.3.x`.
Until that release is published on PyPI, install all packages from the source
checkout as documented in the Quickstart.

## Context schema

The serialized context schema has its own version:

```text
schemas/context-1.0.schema.json
```

Package version changes do not automatically change the context schema version.

A breaking serialized-contract change requires a new context schema version rather than silently changing `1.0`.

## Pre-1.0 API changes

Until 1.0, public Python APIs may evolve between minor releases.

We still aim to:

- document breaking changes in `CHANGELOG.md`;
- use Conventional Commit breaking-change markers;
- keep compatibility aliases where they are cheap and unambiguous;
- avoid changing status semantics silently.

## Core invariants

These are treated as stable product semantics:

- core capability evaluation works offline;
- `UNKNOWN` is never equivalent to `AVAILABLE`;
- missing, stale, and invalid mandatory evidence produce `UNKNOWN`;
- concrete mandatory failures produce `UNAVAILABLE`;
- external publication is opt-in;
- raw telemetry is excluded from publishable snapshots by default;
- network adapters do not control robot actuation.

## External integrations

peaq, ROS 2, MQTT, and HTTP evolve independently.

Sense adapters pin minimum dependency versions where appropriate and CI validates their local contracts.

Live external-network behavior is validated separately from deterministic unit/contract tests.

## Deprecation

A deprecated public API should remain available for at least one minor pre-1.0 release when practical, with a migration path documented in the changelog.

## 1.0 criteria

Sense should only move to 1.0 after:

- the core ingestion and capability contracts have stabilized;
- context schema compatibility is proven across releases;
- adapter boundaries are stable;
- at least one real physical/simulated machine pipeline is operated end-to-end;
- peaq live integration has been verified in a configured environment.
