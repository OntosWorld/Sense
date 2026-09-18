# Security Policy

## Reporting a vulnerability

Do not report security vulnerabilities through a public GitHub issue.

Use GitHub private vulnerability reporting when available, or contact the maintainers privately.

Include:

- affected version or commit;
- reproduction steps;
- expected and actual behavior;
- likely impact;
- any suggested mitigation.

## Security boundaries

### Core SDK

The Sense core is local-first and does not require network access, blockchain credentials, or a hosted backend.

Capability evaluation must not directly actuate hardware. Applications remain responsible for control, safety, authorization, and functional-safety requirements.

### peaq credentials

The `sense-peaq` package receives a configured official `PeaqosClient`.

Sense does not implement its own wallet or key store. Depending on how the peaq client is configured, signing may use environment-provided credentials or peaq-supported wallet mechanisms.

Never log, serialize, commit, or include in telemetry:

- private keys;
- seed phrases;
- wallet exports;
- API keys;
- agent pairing tokens;
- passwords or passphrases.

### Telemetry privacy

Raw machine telemetry stays local by default.

`ContextSnapshot.publishable_view()` removes raw observations unless paths are explicitly allowlisted.

`PeaqContextPublisher.publish_snapshot()` also excludes observations by default and requires an explicit allowlist before raw evidence can be included.

Applications should publish the smallest useful amount of context.

### peaq event trust

Sense defaults peaq Activity Events to the self-reported trust level.

Sense must not label locally-derived context as on-chain-verifiable or hardware-signed unless the caller has the provenance required by peaq for that trust level.

### Input validation

Treat machine telemetry as untrusted input.

Validate:

- paths;
- timestamps;
- TTL values;
- structured payload shape where the application has a domain schema;
- adapter-specific message extraction.

A missing or stale required observation must never result in `AVAILABLE`.

### Network failure behavior

The local capability engine must continue to function when peaq or any other network dependency is unavailable.

Applications should decide explicitly whether a failed external publication should be retried. Do not blindly retry ambiguous blockchain writes.

### ROS 2

The ROS 2 adapter does not provide safety guarantees or ROS graph security.

Use appropriate ROS 2/DDS security, network isolation, namespace policy, QoS, and topic permissions for the deployment.

Do not allow arbitrary remote topic data to become trusted machine state without validation.

## Dependency security

CI runs dependency auditing alongside the normal test/build checks.

Dependencies should be kept small, current, and isolated to optional adapters where possible.

## Supported versions

Sense is currently pre-1.0 software. Security fixes are applied to the actively developed branch and latest published pre-1.0 release.
