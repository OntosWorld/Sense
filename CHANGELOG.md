# Changelog

All notable changes to Sense are documented here.

Sense follows Semantic Versioning and Conventional Commits.

## [Unreleased]

### Added

- canonical telemetry schema and validation layer;
- deterministic raw telemetry normalization;
- built-in unit/value transforms;
- config-driven `SenseConfig`;
- version-aware `CapabilityRegistry`;
- replay/simulator adapter;
- declarative ROS 2 topic-to-Sense bridge;
- MQTT JSON telemetry adapter;
- HTTP polling telemetry adapter;
- nested composed-rule evidence;
- peaq `EventProvenance`;
- local Machine Markets runtime eligibility/candidate filtering;
- opt-in real peaq Activity Event verification test;
- complete raw telemetry pipeline example;
- package release/build workflow;
- compatibility policy.

### Changed

- first-party package line is now `0.3.0`;
- missing, stale, and **invalid** required evidence all produce `UNKNOWN`;
- custom capability evaluator exceptions produce `UNKNOWN`;
- composed rules preserve child outcomes and exact unknown leaf paths;
- ROS 2 mapping reuses the core normalization layer;
- peaq trust level 1 requires a source transaction;
- peaq trust level 2 is rejected until real hardware attestation is integrated;
- CI builds and contract-tests first-party adapter packages.

### Security

- transition observed values remain redacted by default;
- publishable snapshots remain telemetry-free by default;
- peaq provenance cannot be upgraded with an unsupported flag alone.

## [0.2.0] - 2026-09-18

### Fixed

- re-evaluated snapshots as telemetry ages;
- preserved explicit JSON `null`;
- added separate `received_at`;
- supported structured JSON observations;
- aligned context serialization with JSON Schema;
- replaced prototype peaq publishing with official Activity Events;
- removed invented Machine Markets listing endpoints;
- corrected packaging, licensing, CI, and documentation.

### Changed

- heuristic trust scoring was reframed as evidence quality;
- official peaq adapter uses `peaq-os-sdk>=0.8.0`.

## [0.1.0] - 2026-09-18

Initial local-first Python capability-context engine.
