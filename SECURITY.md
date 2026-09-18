# Security Policy

## Reporting a vulnerability

Do not disclose security vulnerabilities through a public issue.

Use GitHub private vulnerability reporting when available, or contact the repository maintainers privately.

Include:

- affected version/commit;
- reproduction steps;
- expected and observed behavior;
- potential impact;
- suggested mitigation if known.

## Security boundaries

Sense is a **context and capability evaluation SDK**. It is not a functional-safety system and must not replace hardware interlocks, emergency-stop systems, certified safety controllers, or OEM safety logic.

An `AVAILABLE` result is application context, not a safety certification.

## Telemetry privacy

Raw machine telemetry remains local by default.

`ContextSnapshot.publishable_view()` excludes raw observations unless the caller explicitly allowlists them.

```python
public = snapshot.publishable_view(
    keep_observations=["battery.level_pct"],
)
```

Review every allowlist before sending machine data outside the local process.

## peaq keys and credentials

Sense does not own or log peaq private keys or seed phrases.

The peaq adapter accepts a configured official `PeaqosClient`. Key custody and transaction signing remain with that client.

Never commit:

- `PEAQOS_PRIVATE_KEY`;
- wallet seed phrases;
- API keys;
- production RPC credentials;
- robot/operator secrets.

Use environment variables or approved secret storage.

## peaq event provenance

Sense defaults peaq Activity Events to trust level `0` for self-reported local context.

Do not configure a higher peaq trust level unless the event actually meets peaq's documented provenance requirements.

## Untrusted input

Treat machine telemetry as untrusted input.

Sense validates observation paths and basic metadata, but domain-specific ranges and semantic validation belong to the application/OEM adapter.

For example, Sense should not invent a universal valid temperature range for every machine.

## ROS 2

Apply ROS 2 security and network controls appropriate to the deployment.

Sense's ROS adapter must not be used to bypass ROS 2 access controls, safety topics, or OEM control boundaries.

## Dependencies

CI runs:

- linting;
- type checking;
- tests;
- package build/install smoke testing;
- dependency auditing.

A failed dependency audit should be investigated before release.

## Logging

Do not add private keys, seed phrases, authorization headers, sensitive raw telemetry, or credentials to logs.

## Supported versions

Sense is pre-1.0. Security fixes are applied to the current development line unless a release policy says otherwise.
