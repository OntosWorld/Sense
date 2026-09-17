# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-17

### Added

- Initial release
- Phase 0: TypeScript project infrastructure with strict mode, ESLint, Prettier, Vitest
- Phase 1: Core data model with TelemetryObservation, NormalizedMachineState, ContextSnapshot
- Phase 2: Capability engine with deterministic rule evaluation (equals, gte, lt, fresh, etc.)
- Phase 3: Transition engine with state-change detection and subscription API
- Phase 4: peaq integration with identity binding and activity event serialization
- Phase 5: Simulator adapter and TelemetryAdapter interface
- Phase 6: MVP demo with warehouse.pick capability
- JSON Schema Draft 2020-12 context schema (version 1.0)
- Full TypeScript type definitions
- JavaScript consumption support
