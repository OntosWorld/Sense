# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability within Sense, please report it responsibly.

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please report them via:

1. GitHub's private vulnerability reporting (if available)
2. Email to the maintainers

When reporting, please include:

- A description of the vulnerability
- Steps to reproduce the issue
- Potential impact of the vulnerability
- Any suggested fixes (optional)

## Security Guidelines

### Private Keys and Secrets

Sense **never** handles private keys or seed phrases. The peaq adapter accepts an already-configured official peaqOS client. The SDK does not provide key custody.

### Telemetry Privacy

Raw machine telemetry remains local by default. Publishing to peaq is always opt-in and requires explicit developer configuration.

### Input Validation

All telemetry observations are validated at the adapter boundary. Malformed data is rejected with typed errors and is never silently accepted into the normalized state store.

### No Automatic Upload

The SDK does not upload telemetry automatically. Developers must explicitly configure and approve what data leaves the process.

### Local-First Core

The core capability evaluation engine works without network access. Blockchain/network operations are never part of the local evaluation hot path.
