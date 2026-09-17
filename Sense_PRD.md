# Sense — Product Requirements Document

> **Working name:** Sense  
> **Document type:** PRD  
> **Status:** Draft for technical validation and peaq partnership discussion  
> **Last verified against peaq documentation:** 2026-09-17

---

## 1. Product Summary

Sense is a **local-first SDK for physical machines**.

It takes raw machine telemetry and developer-defined operating rules and produces a structured, machine-readable view of:

- the machine's current state;
- which capabilities are currently available;
- which capabilities are degraded, unavailable, or unknown;
- the constraints causing those states;
- whether the underlying evidence is fresh enough to use;
- meaningful state transitions that can be published to peaq.

Sense does **not** exist to wrap or rebrand peaq APIs.

Its core value is the transformation:

```text
Raw machine telemetry
        ↓
Normalized physical state
        ↓
Capability + constraint evaluation
        ↓
Current machine context
        ↓
peaq identity / events / market context / data services
```

The SDK runs in the developer's application, robot computer, edge computer, or simulation environment. The first version does **not require a Sense-hosted backend, hosted model, GPU inference service, or separate database service**.

---

## 2. Product Thesis

peaq provides economic infrastructure for machines: identity, credit/reputation, payments, machine services, Machine Markets, and machine data infrastructure.

What is still valuable on top of that infrastructure is a developer layer that can answer:

> **What is this machine actually capable of doing right now, based on its current physical state and constraints?**

A machine may be registered with static capabilities such as `navigation` or `gripper`, but its usable capabilities change continuously because of:

- battery level;
- localization state;
- sensor freshness;
- tool availability;
- safety state;
- component health;
- payload;
- current task;
- operating mode;
- environment or developer-defined constraints.

Sense converts those runtime conditions into structured physical context that can be consumed by software, agents, marketplaces, and peaq services.

---

## 3. Problem

Robotics and machine applications usually expose low-level state:

```text
battery = 34%
motor_temperature = 78°C
localization = valid
gripper = attached
payload = 17kg
maximum_payload = 20kg
emergency_stop = false
```

Those individual values do not directly tell another application:

```text
Can this machine accept a pickup task?
Is navigation currently usable?
Is the machine degraded?
Which constraint is preventing a capability?
Is the information recent enough to trust?
What changed since the previous state?
```

Every developer can implement this logic independently, but doing so repeatedly creates:

- inconsistent machine-state representations;
- custom rules scattered throughout application code;
- duplicated freshness checks;
- poor explainability;
- difficulty integrating live machine state into marketplaces or agent systems;
- difficulty creating consistent machine activity records.

Sense makes this logic a reusable SDK instead of application-specific glue code.

---

## 4. Goals

### 4.1 Primary goals

Sense v1 MUST:

1. ingest machine telemetry from developer applications or adapters;
2. normalize telemetry into a versioned context schema;
3. let developers define capabilities and their operating requirements;
4. evaluate those requirements locally and deterministically;
5. compute freshness from source timestamps and declared TTLs;
6. return explainable capability states;
7. detect meaningful context transitions;
8. integrate with peaqOS without replacing peaqOS;
9. allow selected context transitions to be submitted as peaq activity events;
10. produce a context object suitable for future/current Machine Markets integrations;
11. work without a Sense-hosted backend;
12. expose a stable, documented SDK API.

### 4.2 Secondary goals

The architecture SHOULD allow future support for:

- ROS 2 telemetry adapters;
- MQTT and HTTP adapters;
- TypeScript SDK parity;
- peaq Stream export;
- richer spatial/world context;
- local learned models;
- OEM-specific adapters;
- machine-to-machine context exchange.

---

## 5. Non-Goals

Sense v1 MUST NOT claim to be:

- a robot motion planner;
- an autonomous robot controller;
- a functional-safety system;
- a safety certification layer;
- a world model;
- a hosted AI reasoning service;
- a fleet-management platform;
- a replacement for ROS 2;
- a replacement for peaqOS;
- a replacement for peaq identity, payments, credit, Machine Markets, or Stream;
- a hardware-attestation product.

Sense may provide data that another system uses when making a decision, but it MUST NOT represent a capability result as a formal safety guarantee.

---

## 6. Target Users

### Robotics engineers

Need a repeatable way to convert telemetry and operating rules into a useful runtime representation of a machine.

### Application developers

Need a simple API for querying current machine capability without understanding every sensor topic or OEM-specific state field.

### peaq developers

Need richer physical machine context that can be connected to machine identity, activity events, agents, Machine Markets, and data infrastructure.

### Machine operators and OEM teams

Need machine state represented in a consistent format that can be consumed outside one specific control application.

### Machine agents

Need structured context before selecting services, accepting jobs, or interacting with another machine.

---

## 7. Value Proposition

## 7.1 Value to developers and engineers

Sense provides:

- one structured context model instead of application-specific state objects;
- reusable capability rules instead of duplicated conditional logic;
- freshness and stale-state handling;
- explainable results with the exact constraints that caused a capability state;
- adapters that separate machine-specific telemetry from application logic;
- a local-first runtime with no mandatory external backend;
- a peaq integration path without forcing developers to encode raw telemetry directly into blockchain events;
- testable capability policies that can be exercised in CI without physical hardware.

Example:

```python
context.update("battery.level_pct", 34, observed_at=now)
context.update("safety.estop", False, observed_at=now)
context.update("tool.gripper.available", True, observed_at=now)

result = engine.evaluate("warehouse.pick")

print(result.status)
# AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN

print(result.reasons)
# Structured reasons showing which rule passed or failed
```

The developer owns the rules. Sense executes them consistently.

---

## 7.2 Value to peaq

Sense should provide **new physical-machine context**, not simply abstract peaq's SDK.

### A. Richer machine context for Machine Markets

peaq Machine Markets already supports machines with `capabilities`, runtime profiles, machine context, requirements, and market search.

Sense can supply a runtime answer to:

```text
The machine has capability X
            ↓
Is capability X actually usable now?
            ↓
Why / why not?
```

This can make machine/service matching more physically meaningful.

### B. Better activity evidence

peaq activity events can represent telemetry, data generation, and task completion, with raw data kept off-chain and a `dataHash` stored for integrity.

Sense can turn noisy telemetry into meaningful transitions such as:

```text
navigation: AVAILABLE → UNAVAILABLE
reason: localization_stale

warehouse.pick: AVAILABLE → DEGRADED
reason: payload_margin_low
```

Those transitions are more useful than publishing every raw sensor value.

### C. More meaningful machine economic decisions

peaq's Scale / Machine Markets stack lets agents discover and consume services for machines.

Sense gives an agent an additional physical input before taking economic action:

```text
Can the machine use this service?
Can it accept this task now?
Which physical constraint prevents it?
```

### D. More useful machine history

Structured context events can contribute useful operational history around:

- availability;
- degradation;
- task readiness;
- capability transitions;
- activity;
- operating constraints.

The SDK MUST NOT claim that these events automatically change Machine Credit Rating. peaq's own scoring rules decide how MCR is computed.

### E. Additional peaq service usage

A complete Sense flow can use peaq for:

- machine identity through peaqID;
- activity events;
- machine/agent service discovery through Machine Markets where supported;
- machine-data distribution through Stream in a later phase.

This is a consequence of the product's usefulness, not the product's primary moat.

---

## 7.3 Value to machines

A machine obtains a structured runtime representation of:

```text
What state am I in?
What can I currently do?
What can I not currently do?
What constraint is blocking me?
How recent is the evidence?
What changed?
```

That representation can be used by:

- the machine's own software;
- an external agent;
- another machine;
- a job scheduler;
- a marketplace;
- a fleet application;
- a peaq-integrated service.

Example:

```text
Declared capability:
warehouse.pick

Current state:
battery               31%
gripper               available
localization          valid
payload               19kg
configured max        20kg
estop                  false

Sense:
warehouse.pick = DEGRADED
reason = payload_margin_low
```

The value is not that the machine has more hardware. The value is that software around the machine can reason over its **current usable capability** rather than static metadata.

---

## 8. peaq Integration — Current Confirmed Surface

The peaq integration in this PRD is based on current peaq documentation at:

- https://docs.peaq.xyz/home
- https://docs.peaq.xyz/peaqos/overview
- https://docs.peaq.xyz/peaqos/concepts/peaqid
- https://docs.peaq.xyz/peaqos/concepts/events
- https://docs.peaq.xyz/peaqos/concepts/machine-markets
- https://docs.peaq.xyz/peaqos/functions/scale
- https://docs.peaq.xyz/peaqos/concepts/data-streams
- https://docs.peaq.xyz/peaqos/guides/ros2-machine-runtime
- https://docs.peaq.xyz/peaqos/functions/verify

### 8.1 peaqID / Activate

peaqOS activation gives a machine a peaqID and Machine NFT.

Sense SHOULD bind context to an existing peaq machine identity when the developer provides one.

Sense SHOULD NOT recreate peaq onboarding logic as a competing abstraction.

Example configuration:

```python
machine = ContextMachine(
    peaq_did="did:peaq:...",
    machine_id="..."
)
```

### 8.2 peaq Events

peaq documents two event types:

- revenue;
- activity.

Activity events may represent telemetry, data generation, or task completion.

Sense SHOULD use activity events for selected context transitions.

The raw context payload SHOULD remain local/off-chain by default. A canonical serialized form can be passed as `raw_data` to peaqOS so peaq's SDK computes the event data hash.

Sense MUST respect peaq's documented event constraints, including the metadata size cap documented by peaq.

### 8.3 Machine Markets / Scale

peaq Machine Markets is an orchestration layer that lets a machine agent search services using machine context and requirements.

Sense SHOULD provide an adapter that converts a `ContextSnapshot` into a Machine Markets-compatible context payload.

**Current limitation:** peaq's documentation states that Scale / Machine Markets currently works for Tokenomics 1.0 machines and that Economics 2.0 machines cannot yet register in the Market. Therefore:

- Market integration MUST NOT be a hard dependency for Sense core;
- integration tests MUST target only configurations currently supported by peaq;
- support for newly activated Economics 2.0 machines MUST follow peaq's documented availability;
- the SDK MUST fail clearly rather than pretending Market support exists where peaq does not support it.

### 8.4 peaq Stream

peaq Stream provides signed, encrypted machine-data packages, chunk chains, access grants, and data-sale infrastructure.

Sense MAY later export selected context snapshots or context-event streams into peaq Stream.

This is a later integration, not required for the v1 core.

### 8.5 peaq Verify

peaq currently documents Verify as **coming soon** and states that its details are preliminary.

Sense v1 MUST NOT depend on Verify.

The architecture MAY provide an attestation interface that can consume peaq Verify when a stable SDK/API becomes available.

---

## 9. Core Product Concepts

### 9.1 Telemetry Observation

A single machine observation.

```json
{
  "path": "battery.level_pct",
  "value": 34,
  "observed_at": "2026-09-17T15:00:00Z",
  "source": "battery_controller",
  "ttl_ms": 5000
}
```

Required properties:

- `path`
- `value`
- `observed_at`

Optional properties:

- `source`
- `ttl_ms`
- source-provided quality/confidence metadata

Sense MUST NOT invent a confidence score if the source does not provide one.

---

### 9.2 Context Snapshot

A versioned point-in-time representation of known machine context.

Example:

```json
{
  "schema_version": "1.0",
  "machine": {
    "peaq_did": "did:peaq:..."
  },
  "generated_at": "2026-09-17T15:00:00Z",
  "state": {
    "battery": {
      "level_pct": 34
    },
    "safety": {
      "estop": false
    },
    "localization": {
      "status": "valid"
    }
  },
  "capabilities": {
    "warehouse.pick": {
      "status": "DEGRADED",
      "reasons": [
        {
          "code": "PAYLOAD_MARGIN_LOW",
          "path": "payload.current_kg"
        }
      ]
    }
  }
}
```

---

### 9.3 Capability Definition

A developer-defined description of a machine capability and its requirements.

```python
capability(
    "warehouse.pick",
    requires=[
        equals("tool.gripper.available", True),
        equals("safety.estop", False),
        gte("battery.level_pct", 20),
        fresh("localization.pose", max_age_ms=1000),
    ]
)
```

Sense does not decide what requirements are correct for every robot. The machine developer or OEM defines them.

---

### 9.4 Capability Status

v1 status values:

- `AVAILABLE`
- `DEGRADED`
- `UNAVAILABLE`
- `UNKNOWN`

Definitions:

**AVAILABLE**  
All required evidence exists, is fresh, and all mandatory constraints pass.

**DEGRADED**  
Mandatory constraints still permit operation, but one or more developer-defined warning/degradation rules are active.

**UNAVAILABLE**  
At least one mandatory rule fails.

**UNKNOWN**  
Required evidence is absent, invalid, or too stale to evaluate safely.

`UNKNOWN` MUST NOT be treated as `AVAILABLE`.

---

### 9.5 Constraint Result

Every failed or degraded rule MUST be explainable.

```json
{
  "code": "LOCALIZATION_STALE",
  "severity": "blocking",
  "path": "localization.pose",
  "expected": "age <= 1000ms",
  "observed_age_ms": 4812
}
```

---

### 9.6 Context Transition

A transition occurs when a capability or relevant state changes.

Examples:

```text
AVAILABLE → DEGRADED
DEGRADED → UNAVAILABLE
UNKNOWN → AVAILABLE
```

Transitions can be consumed locally and optionally mapped to peaq activity events.

---

## 10. Functional Requirements

### FR-1: Telemetry ingestion

The SDK MUST provide a programmatic ingestion API.

```python
machine.observe(
    "battery.level_pct",
    34,
    observed_at=timestamp,
    ttl_ms=5000
)
```

The core SDK MUST NOT require ROS 2.

Adapters can map ROS 2, MQTT, HTTP, simulation data, or OEM APIs into the same observation interface.

---

### FR-2: Schema validation

Context data MUST be validated before entering the normalized state store.

The language-neutral serialized schema SHOULD use **JSON Schema Draft 2020-12**.

Official specification:

https://json-schema.org/draft/2020-12

---

### FR-3: Versioned schema

Every serialized Sense context MUST contain a schema version.

Breaking schema changes MUST result in a major schema version.

Unknown extension fields MUST be handled according to documented compatibility rules.

---

### FR-4: Namespaced extensibility

The core schema cannot anticipate every robot.

Developers MUST be able to add namespaced state:

```text
vendor.acme.arm.joint_7.temperature_c
warehouse.zone
perception.object_count
```

Core fields SHOULD remain small and stable.

---

### FR-5: Deterministic rule engine

v1 capability evaluation MUST be deterministic.

Required primitives:

- equality / inequality;
- numeric comparison;
- set membership;
- existence;
- freshness / max age;
- boolean composition: ALL / ANY / NOT;
- warning vs blocking constraints.

No hosted AI model is required.

---

### FR-6: Freshness

Every rule MAY define freshness requirements.

If required evidence exceeds its permitted age, the result MUST become `UNKNOWN` or `UNAVAILABLE` according to the capability definition.

The engine MUST expose the exact stale inputs.

---

### FR-7: Explainability

Every capability evaluation MUST provide:

- status;
- evaluated timestamp;
- evidence used;
- blocking reasons;
- degradation reasons;
- unknown/missing evidence.

---

### FR-8: Transition engine

The SDK MUST detect capability-state transitions.

Developers MUST be able to subscribe:

```python
@machine.on_transition("warehouse.pick")
def handle_transition(event):
    ...
```

The implementation MAY debounce or rate-limit transitions using explicit developer configuration.

---

### FR-9: peaq identity binding

The SDK MUST allow a machine context to be associated with:

- a peaq DID;
- and, where available, a peaq machine ID.

The SDK MUST validate basic identifier shape locally but SHOULD use peaqOS for authoritative peaq state.

---

### FR-10: peaq event publisher

The peaq adapter MUST allow a developer to publish selected Sense transitions as peaq activity events.

Publishing MUST be opt-in.

Default behavior MUST NOT publish all raw telemetry.

Example:

```python
await peaq.publish_transition(
    transition,
    metadata={
        "context_schema": "1.0",
        "capability": "warehouse.pick"
    }
)
```

The peaq adapter MUST rely on the official peaqOS SDK rather than custom contract calls when the required function exists in peaqOS.

---

### FR-11: Machine Markets context adapter

The SDK SHOULD expose:

```python
market_context = Sense.peaq.to_market_context(snapshot)
```

The function converts currently known context into a serializable payload suitable for a peaq Machine Markets request.

The adapter MUST NOT fabricate unsupported peaq fields.

---

### FR-12: Local-only operation

All core functions MUST work with network access disabled.

Only explicit peaq operations require network access.

---

### FR-13: Data minimization

Developers MUST select which fields leave the machine.

Sense MUST support:

- field allowlists;
- field denylists;
- redaction before serialization;
- separate local and publishable context views.

---

### FR-14: Error model

Public SDK errors MUST be typed/classified.

Minimum categories:

- `SchemaValidationError`
- `UnknownCapabilityError`
- `MissingEvidenceError`
- `InvalidRuleError`
- `PeaqConfigurationError`
- `PeaqNetworkError`
- `UnsupportedPeaqFlowError`
- `SerializationError`

Errors MUST contain actionable developer messages and MUST NOT expose private keys or sensitive telemetry by default.

---

## 11. Proposed SDK Surface

### 11.1 Core

```python
from Sense import ContextMachine, capability
from Sense.rules import equals, gte, fresh

machine = ContextMachine(
    machine_ref="robot-001",
    peaq_did="did:peaq:..."
)

machine.define_capability(
    capability(
        "warehouse.pick",
        requires=[
            equals("tool.gripper.available", True),
            equals("safety.estop", False),
            gte("battery.level_pct", 20),
            fresh("localization.pose", max_age_ms=1000),
        ],
        degrade_when=[
            gte("payload.utilization_pct", 90)
        ]
    )
)

machine.observe("battery.level_pct", 34, observed_at=now)
machine.observe("tool.gripper.available", True, observed_at=now)
machine.observe("safety.estop", False, observed_at=now)
machine.observe("localization.pose", pose, observed_at=now, ttl_ms=1000)

result = machine.evaluate("warehouse.pick")
```

### 11.2 Snapshot

```python
snapshot = machine.snapshot()
payload = snapshot.to_dict()
```

### 11.3 peaq adapter

```python
from Sense_peaq import PeaqContextPublisher

publisher = PeaqContextPublisher(peaq_client)

await publisher.publish_transition(
    machine.last_transition("warehouse.pick")
)
```

The exact package names remain working names until registry availability is checked.

---

## 12. Architecture

```text
┌───────────────────────────────────────────────┐
│             Machine / Simulator               │
│                                               │
│ sensors • robot state • OEM API • ROS 2      │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│               Input Adapter                   │
│                                               │
│ converts source data → TelemetryObservation   │
└──────────────────────┬────────────────────────┘
                       │
                       ▼
┌───────────────────────────────────────────────┐
│          Sense Core Runtime              │
│                                               │
│ Schema validation                             │
│ Local normalized state                        │
│ Freshness                                     │
│ Capability rules                              │
│ Constraint evaluation                         │
│ Transition detection                          │
│ Snapshot serialization                        │
└─────────────┬─────────────────┬───────────────┘
              │                 │
              │ local API       │ explicit publish
              ▼                 ▼
       Application / Agent   peaq Adapter
                                │
                ┌───────────────┼──────────────────┐
                ▼               ▼                  ▼
             peaqID          Events          Machine Markets
                                                 context

                               Later:
                              peaq Stream
```

There is no required Sense cloud service in v1.

---

## 13. Adapter Architecture

Adapters MUST implement a small interface rather than coupling the core to one robotics framework.

Conceptual interface:

```python
class TelemetryAdapter(Protocol):
    async def start(self, sink: ObservationSink) -> None: ...
    async def stop(self) -> None: ...
```

This allows:

```text
ROS 2 Adapter
MQTT Adapter
HTTP Adapter
Simulator Adapter
OEM Adapter
        ↓
same Sense core
```

Python `Protocol` is suitable for structural interfaces and is available in the Python standard typing system.

Official Python typing documentation:

https://docs.python.org/3.10/library/typing.html

---

## 14. ROS 2 Integration

ROS 2 SHOULD be the first robotics adapter after the core SDK.

Sense SHOULD follow ROS 2's own communication semantics:

- **topics** for continuous telemetry/state;
- **services** for short request/response operations;
- **actions** only when an integration truly represents a longer-running behavior.

Sense itself is primarily a telemetry consumer, so the adapter SHOULD subscribe to topics rather than invent a new control protocol.

For high-rate sensor topics, adapter configuration MUST expose ROS 2 QoS settings instead of hardcoding one profile.

Official ROS 2 references:

- Topics vs Services vs Actions:  
  https://docs.ros.org/en/ros2_documentation/kilted/How-To-Guides/Topics-Services-Actions.html
- QoS concepts:  
  https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html

peaq already provides a ROS 2 machine runtime for peaqOS functions. Sense MUST NOT duplicate that runtime. The Sense ROS 2 adapter focuses on **reading physical state and generating context**; the peaq adapter handles publishing Sense outputs using supported peaqOS functionality.

peaq ROS 2 reference:

https://docs.peaq.xyz/peaqos/guides/ros2-machine-runtime

---

## 15. Technology Direction

### 15.1 v1 language

**Python first.**

Reason:

- peaqOS officially supports Python;
- peaq's current SDK supports Python 3.10+;
- ROS 2 integrations commonly support Python;
- Python lets the first implementation target robotics engineers directly;
- the canonical JSON schema remains language-neutral so a TypeScript SDK can follow.

### 15.2 Python compatibility

Sense v1 SHOULD target:

```text
Python >= 3.10
```

This aligns with the current peaqOS Python SDK requirement documented by peaq.

### 15.3 Packaging

Use modern Python packaging:

```text
pyproject.toml
src/ layout
tests/
README.md
LICENSE
```

Follow the Python Packaging Authority guidance:

- https://packaging.python.org/en/latest/tutorials/packaging-projects/
- https://packaging.python.org/en/latest/guides/writing-pyproject-toml/

The SDK SHOULD be installable with:

```bash
pip install <package-name>
```

after the final package name is selected and registry availability is confirmed.

---

## 16. Repository Structure

Proposed structure:

```text
Sense/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── SECURITY.md
├── CONTRIBUTING.md
├── schemas/
│   └── context-1.0.schema.json
├── src/
│   └── Sense/
│       ├── __init__.py
│       ├── model/
│       ├── rules/
│       ├── engine/
│       ├── events/
│       ├── adapters/
│       └── serialization/
├── packages/
│   ├── Sense-peaq/
│   └── Sense-ros2/
├── examples/
│   ├── basic-machine/
│   ├── peaq-events/
│   └── ros2/
└── tests/
    ├── unit/
    ├── contract/
    ├── integration/
    └── e2e/
```

The exact monorepo tool is an implementation decision, not a PRD requirement.

---

## 17. Professional Software Engineering Requirements

## 17.1 Public API discipline

The SDK MUST have a clearly documented public API.

Internal modules MUST NOT become accidental public API.

Breaking changes MUST be documented before release.

---

## 17.2 Semantic Versioning

Use Semantic Versioning 2.0.0:

```text
MAJOR.MINOR.PATCH
```

- MAJOR: incompatible public API changes;
- MINOR: backward-compatible functionality;
- PATCH: backward-compatible fixes.

Official specification:

https://semver.org/

Initial development MAY use `0.x.y`. A stable `1.0.0` release means the public API contract is intentionally stable.

---

## 17.3 Schema versioning separate from SDK versioning

The Sense schema version MUST be independent of package version.

Example:

```text
SDK: 0.6.0
Context schema: 1.0
```

An SDK release may support multiple context-schema versions during migrations.

---

## 17.4 Type safety

All public Python APIs MUST include type hints.

Static type checking MUST run in CI.

`Any` SHOULD be avoided in public API surfaces unless unavoidable at an external boundary.

---

## 17.5 Validation at boundaries

Untrusted telemetry MUST be validated at adapter boundaries.

Invalid values MUST NOT silently enter normalized state.

Examples:

- battery percentages outside the declared valid range;
- malformed timestamps;
- unsupported status values;
- invalid rule definitions.

The SDK SHOULD allow domain-specific validation because not every machine uses the same ranges or units.

---

## 17.6 Units

Numeric physical values MUST carry documented units in field names or schema metadata.

Examples:

```text
temperature_c
payload_kg
velocity_mps
battery.level_pct
```

The SDK MUST NOT silently infer units.

---

## 17.7 Time handling

Serialized timestamps MUST use UTC ISO 8601 / RFC 3339-compatible strings.

Freshness calculations SHOULD use a monotonic clock internally where practical, while preserving source observation time separately.

The SDK MUST distinguish:

- when the source says a value was observed;
- when Sense received it;
- when a snapshot was generated.

---

## 17.8 Testing

Required test layers:

### Unit tests

Cover:

- rules;
- freshness;
- state updates;
- transitions;
- schema validation;
- serialization;
- redaction.

### Contract tests

Verify:

- Sense schema contracts;
- peaq adapter serialization;
- errors when peaq-supported flows are unavailable.

### Integration tests

Run against:

- peaq agung testnet where appropriate;
- simulated telemetry;
- ROS 2 test publishers for the ROS adapter.

### End-to-end tests

At minimum:

```text
Simulator
→ telemetry
→ Sense
→ capability transition
→ peaq activity event
→ retrieve/confirm result
```

Network-dependent tests MUST be separable from deterministic local tests.

No release may be published unless unit, contract, type, lint, and packaging checks pass.

---

## 17.9 CI/CD quality gates

Every pull request MUST run:

```text
format check
lint
static type check
unit tests
contract tests
package build
schema validation
dependency/security scan
```

Integration tests requiring peaq network access SHOULD run in a controlled CI job.

Main-branch protection SHOULD require passing checks and code review.

---

## 17.10 Reproducible packaging

Build source distributions and wheels using standard Python packaging.

CI MUST verify that the built package installs in a clean environment.

Release artifacts MUST be created from tagged source.

---

## 17.11 Package supply-chain security

Publishing SHOULD use short-lived trusted CI credentials rather than permanent credentials where the package registry supports it.

Secrets MUST NOT be stored in the repository.

Published packages SHOULD include provenance/attestation where supported by the package registry and CI provider.

---

## 17.12 Dependency policy

Core dependencies SHOULD be kept minimal.

Rules:

- prefer Python standard library where reasonable;
- pin development tooling in the development environment;
- define supported version ranges for runtime dependencies;
- automate dependency-update checks;
- document why security-sensitive dependencies exist;
- do not introduce an external service dependency for functionality that can run locally.

---

## 17.13 Logging

The SDK MUST use structured, configurable logging.

The SDK MUST NOT log:

- private keys;
- seed phrases;
- wallet secrets;
- full sensitive telemetry payloads by default.

Developer debug logging MUST be explicitly enabled.

---

## 17.14 Error handling

Network operations MUST:

- distinguish retryable and non-retryable failures;
- expose transaction identifiers where available;
- avoid automatic duplicate submissions for ambiguous transaction states;
- follow peaq's documented transaction behavior rather than blindly retrying blockchain writes.

---

## 17.15 Documentation

Every public feature MUST include:

- API reference;
- minimal example;
- expected inputs;
- returned outputs;
- error behavior.

Required guides for v1:

1. Quickstart
2. Define a machine
3. Add telemetry
4. Define a capability
5. Evaluate capability
6. Handle stale data
7. Publish a transition to peaq
8. Use with peaq Machine Markets where supported
9. ROS 2 adapter
10. Security and key-handling guidance

---

## 18. Security and Privacy Requirements

### SR-1: Private-key ownership

Sense core MUST NOT require custody of peaq private keys.

The peaq adapter SHOULD accept an already configured official peaqOS client/signer.

### SR-2: No automatic telemetry upload

Raw telemetry MUST remain local unless the developer explicitly configures publication.

### SR-3: Publish allowlist

peaq publishing MUST use an explicit field allowlist or explicit event serializer.

### SR-4: Redaction

Sensitive paths MUST support redaction before a snapshot leaves the process.

### SR-5: No unsafe control side effects

Core evaluation MUST be read-only with respect to machine control.

A capability result cannot directly move a robot.

### SR-6: No false attestation claims

Sense MUST distinguish:

- locally derived context;
- peaq event integrity;
- machine-level attestation.

Until peaq Verify is available and integrated according to its final specification, Sense MUST NOT market locally derived context as hardware-attested by peaq.

---

## 19. Performance Requirements

The core evaluation engine SHOULD be lightweight enough to run on an edge computer without GPU hardware.

Initial targets for a typical context containing hundreds of fields and tens of capability rules:

- no network dependency for evaluation;
- deterministic memory usage relative to configured state history;
- capability evaluation suitable for sub-second operational use;
- no blocking blockchain call in the local evaluation path.

Exact latency targets MUST be benchmarked before being made contractual.

---

## 20. MVP Scope

The MVP should prove one complete workflow.

### Demo machine

Use a simulator or ROS 2-enabled robot.

### Telemetry

At minimum:

```text
battery.level_pct
safety.estop
localization.status
tool.gripper.available
payload.current_kg
payload.max_kg
```

### Capability

```text
warehouse.pick
```

### Example rules

```text
battery >= threshold
estop == false
localization == valid and fresh
gripper == available
payload <= configured maximum
```

### Output

```text
AVAILABLE
DEGRADED
UNAVAILABLE
UNKNOWN
```

with reasons.

### peaq integration

For the supported machine generation/configuration:

1. bind the local machine context to a peaqID;
2. generate a context transition;
3. serialize the selected transition;
4. submit it as a peaq activity event using the official peaqOS SDK;
5. retain raw detailed context locally;
6. verify that the peaq event was submitted and can be associated with the machine.

### Optional market demonstration

If using a peaq machine configuration currently supported by Machine Markets:

```text
Sense snapshot
        ↓
Machine Markets context
        ↓
service search
```

Do not block MVP completion on Market support for Economics 2.0 machines while peaq documents that support as unavailable.

---

## 21. Development Plan

### Phase 0 — Technical validation

Deliver:

- confirmed peaqOS SDK calls required for activity-event submission;
- peaq Agung testnet setup;
- JSON context-schema draft;
- one deterministic capability rule;
- local proof of concept.

Exit criteria:

```text
telemetry → context → capability result
```

works entirely locally.

---

### Phase 1 — Core SDK

Build:

- observation model;
- state store;
- JSON Schema validation;
- freshness engine;
- rule engine;
- capability result;
- transition detection;
- serializer;
- typed errors;
- documentation;
- unit tests.

Exit criteria:

A developer can install the package and implement the full local workflow without peaq.

---

### Phase 2 — peaq adapter

Build:

- peaq DID/machine reference binding;
- official peaqOS SDK integration;
- activity-event serializer;
- `raw_data` handling;
- transaction result/error handling;
- Agung integration tests.

Exit criteria:

A selected Sense transition is successfully submitted as a peaq activity event without uploading all raw telemetry.

---

### Phase 3 — ROS 2 adapter

Build:

- configurable topic subscriptions;
- topic → Sense path mappings;
- configurable QoS;
- timestamps;
- lifecycle start/stop;
- ROS 2 examples and tests.

Exit criteria:

ROS 2 telemetry updates Sense context and drives capability transitions.

---

### Phase 4 — Machine Markets adapter

Build only against currently supported peaq interfaces.

Deliver:

- ContextSnapshot → Machine Markets context mapping;
- service-search example;
- compatibility/error handling for unsupported machine generations.

Exit criteria:

A supported peaq machine can use current Sense context as an input to a Machine Markets search without Sense inventing unsupported peaq data.

---

### Phase 5 — Stream integration

Optional after the core product proves useful.

Explore:

- context snapshots as machine-data products;
- context-transition datasets;
- field-level publication policy;
- integration with peaq Stream packaging.

---

## 22. Acceptance Criteria for v1

v1 is acceptable when all of the following are true:

- [ ] Package installs cleanly on a supported Python version.
- [ ] Core works offline.
- [ ] Context schema is versioned and validated.
- [ ] Developer can ingest telemetry programmatically.
- [ ] Developer can define at least one custom capability.
- [ ] Freshness changes capability status correctly.
- [ ] Missing required evidence results in `UNKNOWN`, not a false positive.
- [ ] Capability result includes structured reasons.
- [ ] Transitions are emitted only when state meaningfully changes.
- [ ] Raw telemetry is not sent externally by default.
- [ ] peaq adapter uses official peaqOS SDK functionality.
- [ ] A transition can be submitted as a peaq activity event on the supported test configuration.
- [ ] Peaq network errors are explicit and do not corrupt local state.
- [ ] Machine Markets adapter does not claim unsupported Economics 2.0 Market functionality.
- [ ] No v1 feature depends on peaq Verify.
- [ ] Public APIs are typed and documented.
- [ ] CI passes formatting, lint, type checking, tests, schema validation, and package-build checks.
- [ ] Security documentation explains key custody and telemetry publication behavior.

---

## 23. Success Metrics

Initial product metrics:

### Developer usefulness

- time required to integrate one machine telemetry source;
- time required to define one capability;
- number of lines of application-specific state logic replaced by Sense;
- percentage of capability results containing actionable reasons;
- successful local use without Sense infrastructure.

### peaq usefulness

- number of Sense-enabled machines associated with peaq identities;
- number of meaningful context-transition activity events submitted;
- number of Sense-based Machine Markets searches once supported;
- number of developers using both Sense and peaqOS;
- number of peaq ecosystem projects/OEMs that can reuse the same Sense schema or capability model.

### Machine usefulness

- percentage of machine decisions where current capability can be determined from fresh evidence;
- number of blocked/degraded states correctly surfaced before application-level task assignment;
- reduction in stale-state decisions in reference integrations.

These are product metrics to measure after implementation; they are not current claims.

---

## 24. Partnership Value to peaq

A peaq partnership makes sense if Sense proves that it adds a physical-machine capability layer peaq does not need to build itself.

The partnership case is:

> **peaq provides the machine's economic infrastructure. Sense turns live physical machine state into structured capability context that peaq applications, agents, events, and markets can use.**

Sense contributes:

1. a versioned physical-context schema;
2. a local machine-state engine;
3. freshness handling;
4. capability/constraint evaluation;
5. explainable capability state;
6. machine-context transitions;
7. adapters for bringing robot telemetry into this context;
8. a peaq integration that makes the resulting context economically useful.

peaq contributes:

1. machine identity;
2. machine economic state;
3. activity-event infrastructure;
4. Machine Markets / agent service orchestration where supported;
5. machine-data infrastructure;
6. future machine attestation infrastructure.

The product should be positioned as **new value built on peaq**, not as a convenience wrapper around peaq.

---

## 25. Open Questions Requiring Validation

These must be resolved during implementation or directly with peaq:

1. What machine-context fields does peaq recommend partners provide to `POST /market/search` beyond the current documented examples?
2. What is peaq's preferred partner process for proposing a new Machine Markets skill/service category?
3. When will Economics 2.0 machines be supported by Scale / Machine Markets?
4. Which context transitions, if any, does peaq consider useful input to MCR or other machine-history products?
5. Should context-event metadata follow a partner-specific namespace convention?
6. Does peaq want Sense context exposed through Machine Markets, Stream, both, or a separate partner service?
7. What canonical machine/OEM demo would peaq consider most useful for partnership validation?

The SDK MUST NOT invent answers to these questions. They require peaq confirmation.

---

## 26. Official References

### peaq

- peaq documentation home: https://docs.peaq.xyz/home
- peaqOS overview: https://docs.peaq.xyz/peaqos/overview
- peaqOS install: https://docs.peaq.xyz/peaqos/install
- peaqID: https://docs.peaq.xyz/peaqos/concepts/peaqid
- Events: https://docs.peaq.xyz/peaqos/concepts/events
- Machine Markets: https://docs.peaq.xyz/peaqos/concepts/machine-markets
- Scale: https://docs.peaq.xyz/peaqos/functions/scale
- Data streams: https://docs.peaq.xyz/peaqos/concepts/data-streams
- ROS 2 machine runtime: https://docs.peaq.xyz/peaqos/guides/ros2-machine-runtime
- Verify: https://docs.peaq.xyz/peaqos/functions/verify

### SDK/schema/software engineering

- JSON Schema Draft 2020-12: https://json-schema.org/draft/2020-12
- Python Packaging User Guide: https://packaging.python.org/en/latest/
- Packaging Python Projects: https://packaging.python.org/en/latest/tutorials/packaging-projects/
- `pyproject.toml` guidance: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- Python typing: https://docs.python.org/3.10/library/typing.html
- Semantic Versioning 2.0.0: https://semver.org/

### ROS 2

- ROS 2 Topics vs Services vs Actions: https://docs.ros.org/en/ros2_documentation/kilted/How-To-Guides/Topics-Services-Actions.html
- ROS 2 QoS concepts: https://docs.ros.org/en/humble/Concepts/Intermediate/About-Quality-of-Service-Settings.html

---

## 27. One-Sentence Definition

**Sense is a local-first SDK that turns raw machine telemetry into structured, explainable current capability and constraint context, then lets developers connect that context to peaq's machine identity, activity, market, and data infrastructure.**
