# Security Policy

## Reporting a vulnerability

Do not disclose vulnerabilities through a public issue.

Use GitHub private vulnerability reporting when available, or contact the
maintainers privately.

Include the affected version/commit, reproduction, impact, and mitigation if
known.

## Product boundary

Sense is a machine-context SDK, not a functional-safety system.

An `AVAILABLE` result must never replace hardware interlocks, emergency-stop
systems, certified safety controllers, OEM safety logic, or authorization.

## Untrusted telemetry

Treat all incoming machine data as untrusted.

Sense 0.3.x can validate:

- canonical path declarations;
- JSON-compatible values;
- expected type;
- nullability;
- numeric bounds;
- enum values;
- source TTL.

Validation failure is preserved on the observation and mandatory invalid
evidence becomes `UNKNOWN`.

Domain-specific semantic validation still belongs in the deployment/OEM schema.

## Normalization

Transforms execute inside the local process.

Custom transforms must be deterministic, bounded, and must not perform hidden
network or actuation side effects.

Do not use transforms to silently repair safety-critical evidence.

## Telemetry privacy

Raw observations remain local by default.

`publishable_view()` removes observations unless explicitly allowlisted.

peaq transition reason values are also redacted unless
`include_observed_values=True` is supplied.

Review every allowlist and metadata payload before external publication.

## Transport adapters

### ROS 2

Use DDS/ROS security, namespaces, QoS, and network controls appropriate to the
deployment. Sense does not bypass ROS permissions.

### MQTT

Use TLS/authentication where required. Do not hard-code broker credentials in
mapping files or repository source.

### HTTP

Prefer authenticated TLS endpoints on untrusted networks. Do not commit
authorization headers or machine credentials.

Adapter network failures must not change local evidence into a false
`AVAILABLE` result.

## peaq credentials

Sense receives a configured official `PeaqosClient`; it does not implement a
wallet or key store.

Never commit private keys, seed phrases, API keys, pairing tokens, or RPC
credentials.

## peaq provenance

Default Activity Events are self-reported/off-chain.

Trust level 1 requires a real source transaction and supported source chain.

Sense currently rejects trust level 2 rather than asserting hardware-signed
provenance without an attested hardware source.

## Live tests

`tests/live/` can create real external transactions.

They are disabled by default and require explicit environment flags. Never
enable live transaction tests in untrusted pull requests.

## Dependencies and release

CI includes tests, strict typing, lint/format checks, package builds, adapter
contract/build checks, schema validation, and dependency auditing.

Investigate failed audits before release.

## Logging

Do not log secrets, authorization headers, private telemetry, pairing tokens, or
wallet material.

## Supported versions

Sense is pre-1.0. Security fixes target the active release line unless a separate
support policy is announced.
