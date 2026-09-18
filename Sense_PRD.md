# Sense Product Requirements Document

**Product:** Sense  
**Repository:** `OntosWorld/Sense`  
**Primary language:** Python 3.10+  
**Current pre-1.0 package version:** 0.2.0  
**Context schema:** 1.0  
**License:** Apache-2.0

## 1. Product summary

Sense is a local-first SDK for physical machines.

It converts raw machine telemetry into structured, explainable current capability and constraint context.

```text
raw machine telemetry
        ↓
validated observations
        ↓
freshness / validity
        ↓
capability + constraint evaluation
        ↓
AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
        ↓
structured reasons
        ↓
meaningful state transitions
        ↓
optional external integrations
```

The core product answers:

> What can this physical machine actually do right now, what prevents it from doing something, and how fresh is the evidence behind that answer?

## 2. Product thesis

Machine identity and static capability metadata do not describe current physical readiness.

A robot may be registered as a machine that can pick, navigate, inspect, or deliver while its current battery, localization, tool state, payload, temperature, emergency stop, or other physical evidence makes that capability temporarily unusable.

Sense turns live machine state into a deterministic runtime capability layer.

## 3. Product boundaries

Sense is:

- a machine-context SDK;
- a deterministic capability evaluator;
- a freshness and evidence layer;
- an explainable transition generator;
- local-first and usable offline;
- extensible through adapters.

Sense is not:

- a robot controller;
- a motion planner;
- a functional-safety system;
- a safety certification layer;
- a world model;
- a fleet-management platform;
- a hosted Sense backend;
- a required cloud service;
- a replacement for ROS 2;
- a replacement for peaqOS;
- a competing machine marketplace;
- a machine identity system;
- a general machine-trust or credit-rating system.

The capability-evaluation hot path must never require blockchain or network calls.

## 4. Target users

Primary users:

- robotics engineers;
- physical-AI engineers;
- machine/OEM software developers;
- developers building agents or applications that consume physical-machine state;
- peaq ecosystem developers who need current physical context.

## 5. Core value

### For developers

Sense provides:

- a common observation model;
- reusable capability definitions instead of scattered conditionals;
- deterministic freshness handling;
- explicit `UNKNOWN` behavior;
- structured reasons;
- meaningful transition events;
- versioned serialization;
- privacy controls;
- transport-independent core logic;
- testable machine policy without requiring physical hardware.

### For machines and agents

Sense provides a structured answer to:

- what state is known;
- what capabilities are usable now;
- what capabilities are degraded;
- what capabilities are unavailable;
- what is unknown;
- what evidence is stale or missing;
- what changed since the last evaluation.

### For peaq applications

peaq provides machine identity, events, economic infrastructure, orchestration, services, and Machine Markets.

Sense contributes current physical capability context derived from live machine evidence.

The intended separation is:

```text
Sense
live physical context + current capability

peaq
machine identity + events + orchestration + economic infrastructure
```

## 6. Core architecture

```text
Telemetry source
      ↓
TelemetryObservation
      ↓
Observation store
      ↓
Constraint rules
      ↓
CapabilityResult
      ↓
ContextTransition
      ↓
ContextSnapshot
```

External adapters remain outside the core:

```text
ROS 2 ─┐
MQTT ──┤
HTTP ──┼──> Sense core
OEM ───┤
Sim ───┘

Sense core ──> optional peaq adapter
```

## 7. Telemetry observation model

A telemetry observation represents one current piece of machine evidence.

Required concepts:

- `path`;
- `value`;
- `observed_at`;
- `received_at`;
- optional `source`;
- optional `ttl_ms`.

Values must support JSON-compatible data:

- null;
- boolean;
- number;
- string;
- array;
- object.

This is required for structured robotics data such as poses, vectors, health summaries, and tool state.

### Time semantics

`observed_at` = when the source measured the value.

`received_at` = when Sense received the value.

`evaluated_at` = when a capability was evaluated.

`generated_at` = when a snapshot was generated.

These timestamps must not be silently collapsed into one another.

## 8. Freshness and validity

Freshness is a first-class product feature.

An observation may specify `ttl_ms`, representing the maximum lifetime of that observation.

Once the observation exceeds its TTL, it is stale evidence.

A capability may also impose a stricter requirement:

```python
fresh("localization.pose", max_age_ms=1000)
```

An observation used by a rule must satisfy both:

1. its source-level TTL, when defined;
2. the capability-specific freshness rule, when defined.

Missing or stale evidence for a blocking requirement must produce `UNKNOWN`, never `AVAILABLE`.

Snapshots must be reevaluated when requested because time can change freshness even if no new observation arrives.

## 9. Capability model

A capability is a named decision unit.

Examples:

```text
warehouse.pick
warehouse.place
navigation.indoor
inspection.ready
delivery.ready
```

A capability contains:

- blocking requirements;
- optional degradation conditions;
- metadata/description/version as needed.

Example:

```python
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
            gte("payload.utilization_pct", 90),
        ],
    )
)
```

## 10. Capability statuses

### AVAILABLE

Required evidence exists, is valid/fresh enough, and all blocking constraints pass.

### DEGRADED

All blocking requirements pass, but a developer-defined degradation condition is active.

### UNAVAILABLE

At least one blocking requirement fails with concrete current evidence.

### UNKNOWN

Required evidence is missing or stale, or a safe determination cannot be made.

Critical invariant:

> `UNKNOWN` must never be silently treated as `AVAILABLE`.

## 11. Rule engine

The v1 deterministic rule engine should support:

- equality;
- numeric comparison;
- membership;
- existence;
- freshness;
- logical ALL;
- logical ANY;
- logical NOT;
- supported composition helpers such as NONE_OF and ONLY_ONE.

Rules must be deterministic and local.

Rules should return structured outcomes containing:

- code;
- path;
- expected condition;
- observed value;
- observed age;
- absence/staleness flags.

## 12. Explainability

Every non-available result must be explainable without parsing arbitrary log text.

`CapabilityResult` includes:

- status;
- blocking reasons;
- warnings;
- unknown paths;
- evaluation time.

Reason codes should be stable enough for application logic, logging, dashboards, and event serialization.

## 13. Transitions

Sense records meaningful capability status changes.

Examples:

```text
UNKNOWN → AVAILABLE
AVAILABLE → DEGRADED
DEGRADED → UNAVAILABLE
AVAILABLE → UNKNOWN
UNAVAILABLE → AVAILABLE
```

A transition contains:

- capability;
- previous status;
- current status;
- timestamp;
- structured reasons.

Repeated evaluation with the same status must not create duplicate transitions.

## 14. Context snapshots

`ContextSnapshot` is the canonical versioned machine-context output.

It contains:

- independent schema version;
- machine reference;
- optional peaq DID binding;
- generation time;
- normalized current state;
- observations;
- evaluated capabilities;
- blocking reasons;
- warnings;
- unknown paths;
- optional trace identifier.

The language-neutral representation uses JSON Schema Draft 2020-12.

The context schema version is independent from the Python package version.

## 15. Privacy and data minimization

Raw machine telemetry remains local by default.

Sense supports:

- observation allowlists;
- observation denylists;
- capability allowlists;
- capability denylists;
- local views;
- publication-safe views.

`publishable_view()` must exclude raw observations by default.

A developer must explicitly allow observation paths before external publication.

## 16. peaq integration

The peaq adapter must use current official peaqOS APIs.

Python dependency:

```text
peaq-os-sdk >= 0.8.0
```

Client:

```python
from peaq_os_sdk import PeaqosClient
```

Sense must not invent blockchain methods, DID document extensions, listing APIs, or market endpoints.

### 16.1 Machine identity

Sense may associate local context with an existing peaq machine identity or machine ID.

Sense does not create a competing identity system.

### 16.2 Activity Events

Meaningful Sense transitions are a natural fit for peaq Activity Events.

```text
Sense transition
    ↓
selected/redacted JSON
    ↓
PeaqosClient.submit_event()
    ↓
peaq Activity Event
```

Default event behavior:

- `EVENT_TYPE_ACTIVITY`;
- value `0`;
- empty currency;
- self-reported trust level unless explicitly justified otherwise;
- compact metadata;
- raw machine telemetry excluded unless explicitly allowlisted.

Sense must not claim locally-derived context is hardware-signed or on-chain-verifiable unless the required provenance exists.

### 16.3 Machine Markets

Machine Markets integration must delegate to the official:

```python
client.orchestration
```

Examples of supported wrapper targets include current documented methods such as:

- `list_machines`;
- `list_market_services`;
- `get_market_service`;
- `search_market`.

Sense must not implement a parallel listing registry.

Sense runtime context can be used by an application alongside peaq market results to answer:

> Is this machine physically capable of performing this service right now?

### 16.4 Network behavior

peaq operations are opt-in.

Network failure must not break local capability evaluation.

Ambiguous blockchain transactions must not be blindly retried.

## 17. ROS 2 integration

ROS 2 remains an optional adapter.

The desired adapter flow is:

```text
ROS topic
    ↓
message field extraction
    ↓
Sense observation path
    ↓
timestamp / source / TTL
    ↓
ContextMachine.observe()
```

The core must not require ROS 2.

Near-term ROS work:

- declarative topic-to-path mapping;
- common message extractors;
- QoS configuration;
- source timestamp preservation;
- real ROS workspace integration tests.

## 18. Experimental context quality

A deterministic evidence-quality module may score factors such as freshness, coverage, staleness, and diversity.

This is optional and experimental.

It must not be positioned as:

- peaq event trust;
- Machine Credit Rating;
- hardware attestation;
- a safety score;
- general machine trustworthiness.

The core capability status remains the authoritative Sense decision output.

## 19. Packaging

Core package:

```text
sense-ai
```

Optional adapters:

```text
sense-peaq
sense-ros2
```

Requirements:

- Python 3.10+;
- `pyproject.toml`;
- typed package marker;
- Apache-2.0;
- SemVer;
- pre-1.0 versions until the public contract stabilizes.

## 20. Repository structure

```text
src/sense_ai/
  model/
  rules/
  events/
  serialization/
  trust/
  errors.py

packages/
  Sense-peaq/
  Sense-ros2/

schemas/
tests/
examples/
docs/
```

Generated Python bytecode and caches must not be tracked.

## 21. Engineering quality

Required gates include:

- formatting;
- linting;
- strict type checking;
- unit tests;
- contract tests;
- integration tests;
- core end-to-end tests;
- schema validation;
- distribution build;
- built-wheel installation smoke test;
- dependency audit.

The rule engine is not exempt from static typing.

## 22. Test strategy

### Unit

Cover:

- observation validation;
- structured values;
- observed/received timestamps;
- TTL;
- freshness;
- rule outcomes;
- all four capability states;
- transitions;
- privacy/redaction.

### Contract

Cover:

- JSON Schema validity;
- snapshot round-trip;
- stable serialized capability evidence.

### Integration

Cover:

- complete local machine lifecycle;
- transitions over changing evidence.

### peaq adapter contract

Mock only the official peaqOS boundary.

Do not mock fictional network endpoints.

### Live peaq

Live testnet/network verification remains opt-in and credential-dependent.

Do not make normal pull requests depend on network availability or funded wallets.

## 23. MVP acceptance flow

```text
simulated or real telemetry
        ↓
Sense
        ↓
warehouse.pick
        ↓
AVAILABLE / DEGRADED / UNAVAILABLE / UNKNOWN
        ↓
structured reason
        ↓
transition
        ↓
optional peaq Activity Event
```

Example evidence:

```text
battery.level_pct
safety.estop
localization.pose
tool.gripper.available
payload.current_kg
payload.max_kg
```

## 24. Success criteria

Sense is successful when a developer can:

1. install the core SDK;
2. define machine capabilities in readable rules;
3. ingest real or simulated telemetry;
4. receive deterministic current capability state;
5. understand exactly why a state was produced;
6. observe stale evidence becoming `UNKNOWN`;
7. serialize a language-neutral snapshot;
8. publish only selected context externally;
9. optionally submit meaningful transitions through the official peaqOS SDK;
10. use Sense runtime context alongside peaq orchestration without duplicating peaq functionality.

## 25. Roadmap

### Current core

- observation model;
- deterministic capability rules;
- freshness/TTL;
- transitions;
- versioned snapshots;
- data minimization.

### Near term

- complete peaq Activity Event verification on testnet;
- expand official orchestration integration where it provides real product value;
- finish ROS 2 topic mapping;
- tighten public API stability;
- expand package smoke tests and docs execution.

### Later

- TypeScript/Rust/C++ implementations may consume the same language-neutral schema if ecosystem demand justifies them;
- additional transport adapters;
- peaq Stream integration only when a concrete use case is validated.

## 26. Official references

- peaqOS: https://docs.peaq.xyz/home
- peaqOS install: https://docs.peaq.xyz/peaqos/install
- peaq Python SDK: https://docs.peaq.xyz/peaqos/sdk-reference/sdk-python
- peaq Events: https://docs.peaq.xyz/peaqos/concepts/events
- peaq event guide: https://docs.peaq.xyz/peaqos/guides/submit-events
- peaq Machine Markets: https://docs.peaq.xyz/peaqos/concepts/machine-markets
- peaq orchestration Python SDK: https://docs.peaq.xyz/peaqos/sdk-reference/orchestration-py
- ROS 2: https://docs.ros.org/
- JSON Schema 2020-12: https://json-schema.org/draft/2020-12
- Semantic Versioning: https://semver.org/
- Conventional Commits: https://www.conventionalcommits.org/en/v1.0.0/
