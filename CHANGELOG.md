# Changelog

All notable changes to Sense are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Replaced the speculative peaq publisher with an adapter over the official `peaq-os-sdk` Python client.
- Sense capability transitions and snapshots are now submitted as peaq Activity Events.
- Replaced the custom Machine Markets listing API with a thin wrapper over the official `PeaqosClient.orchestration` namespace.
- External `publishable_view()` output now excludes raw observations by default.
- Snapshot generation now reevaluates time-sensitive capability state instead of returning a cache based only on observation count.
- Observation TTL is enforced across constraints.
- Observation values now support structured JSON-compatible data.
- Added separate `received_at` timestamps and transport-delay tracking.
- Capability snapshots now preserve blocking reasons, warnings, and unknown paths across serialization.
- Capability transitions now carry structured reasons.
- Package and adapter versions are aligned at `0.2.0`.
- Package licensing and repository metadata are aligned with Apache-2.0 and `OntosWorld/Sense`.
- Python bytecode/cache artifacts are no longer tracked.

### Fixed

- Fixed stale `AVAILABLE` snapshots when telemetry aged without a new observation.
- Fixed schema round-trip loss of capability evidence.
- Fixed CI type-check and security-job configuration.
- Removed stale TypeScript documentation and examples.
- Removed duplicate `sense_ai.trust` module ambiguity.

### Security

- Raw telemetry requires an explicit allowlist before snapshot publication through the peaq adapter.
- Sense does not automatically upgrade peaq event trust level beyond self-reported.

## [0.1.0] - 2026-09-17

### Added

- Initial local-first Python capability evaluation engine.
- `TelemetryObservation`, `ContextMachine`, `ContextSnapshot`, and capability result types.
- Deterministic rule engine with comparison, existence, freshness, and logical composition.
- `AVAILABLE`, `DEGRADED`, `UNAVAILABLE`, and `UNKNOWN` capability states.
- Transition detection and event callbacks.
- Versioned JSON Schema Draft 2020-12 context representation.
- Snapshot redaction helpers.
- Initial ROS 2 adapter groundwork.
- Unit, contract, integration, and end-to-end test structure.
