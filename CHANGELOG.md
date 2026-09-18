# Changelog

All notable changes to Sense are documented here.

This project follows Semantic Versioning and Conventional Commits.

## [Unreleased]

### Fixed

- re-evaluate snapshots so freshness can expire without new telemetry;
- preserve explicit JSON `null` telemetry while adding `get_observation()`;
- add `received_at` and structured JSON telemetry values;
- align snapshot serialization with the versioned JSON Schema;
- make `publishable_view()` exclude raw telemetry by default;
- add serializable capability transitions;
- consolidate duplicate event and evidence-quality implementations;
- replace prototype peaq DID-document publishing with official peaq Activity Events;
- remove the custom Machine Markets `/listings` model and delegate to peaq orchestration;
- correct package license, repository URLs and version metadata;
- repair CI type-check, e2e, build-smoke and dependency-audit gates.

### Changed

- canonical package version is `0.2.0` while the public API stabilizes;
- heuristic “trust” scoring is now described as **evidence quality** to avoid conflict with peaq protocol trust levels;
- peaq adapter depends on `peaq-os-sdk>=0.4.0`;
- documentation now uses the actual Python API and current peaqOS integration model.

## [0.1.0] - 2026-09-18

Initial development release of the local-first Sense capability-context engine.
