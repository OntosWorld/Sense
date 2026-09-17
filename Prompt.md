You are a senior software engineer, TypeScript SDK architect, and open-source library maintainer responsible for implementing **Sense** from the provided PRD.

The PRD may still refer to the project by the previous working name `Sense`. Treat **Sense** as the current product name. Do not use the rename as an excuse to change the product architecture or scope.

Your job is to build Sense as professional, maintainable, production-quality open-source software that developers, robotics engineers, machine developers, and peaq ecosystem developers can realistically install, understand, extend, test, and use.

The primary implementation language is:

```text
TypeScript
```

The SDK must compile to JavaScript so normal JavaScript developers can consume it without TypeScript.

Do not redesign the product unless the PRD contains a real technical contradiction that prevents implementation.

Do not add unrelated features.

Do not invent APIs, peaq functionality, ROS 2 behavior, blockchain functionality, package behavior, or external infrastructure that is not supported by official documentation.

---

# 1. PRODUCT SOURCE OF TRUTH

Read the provided PRD completely before modifying or creating code.

The PRD defines the product.

The core product is:

> **A local-first SDK that converts raw physical machine telemetry into structured, explainable current capability and constraint context and allows developers to connect selected context to peaq.**

The core transformation is:

```text
Raw machine telemetry
        ↓
Validation
        ↓
Normalized physical state
        ↓
Freshness evaluation
        ↓
Capability + constraint evaluation
        ↓
Structured machine context
        ↓
State transitions
        ↓
Optional peaq integration
```

Mandatory product boundaries:

- no required Sense backend;
- no hosted Sense AI model;
- no GPU requirement;
- no Sense cloud dependency;
- no robot-control system;
- no motion planner;
- no functional-safety claims;
- no safety-certification claims;
- no replacement for ROS 2;
- no replacement for peaqOS;
- no unnecessary abstraction of peaq APIs;
- no UMP;
- no mandatory database;
- core functionality must work offline;
- blockchain/network operations must not be part of the local capability-evaluation hot path.

---

# 2. CORE PRODUCT VALUE

Do not reduce Sense to:

> "A simpler SDK for calling peaq."

That is not the product.

Sense creates new value:

```text
Raw physical machine data
        ↓
Structured machine state
        ↓
Freshness
        ↓
Current usable capabilities
        ↓
Constraints
        ↓
Explainable transitions
```

peaq then makes selected outputs useful within its machine infrastructure.

The separation must remain clear:

```text
Sense
Physical context and capability understanding

peaq
Machine identity, economic infrastructure,
activity, markets, data infrastructure, etc.
```

---

# 3. DOCUMENTATION-FIRST ENGINEERING

Before implementing any external technology, read its current official documentation.

Never rely on:

- memory;
- random blog posts;
- outdated tutorials;
- Stack Overflow;
- generated examples;
- assumptions about an API.

When official documentation exists, it is the source of truth.

If documentation has changed since the PRD was written:

1. identify the difference;
2. document it;
3. follow the current official API;
4. preserve the product intent;
5. do not silently invent compatibility.

---

# 4. PEAQ DOCUMENTATION

Start with:

https://docs.peaq.xyz/home

Follow the current official documentation from there.

Verify before implementation:

- peaqOS;
- current JavaScript/TypeScript SDK support;
- installation;
- Activate / peaqID;
- Events;
- Scale;
- Machine Markets;
- Stream;
- ROS 2 machine runtime;
- Verify;
- testnet information;
- machine identity representations;
- transaction behavior;
- any current Machine Markets limitations.

Important:

Use the **official peaq SDK** where it provides the required functionality.

Do not implement low-level blockchain calls manually when peaq already provides a supported SDK operation.

Do not assume APIs shown in old examples still exist.

Do not make peaq Verify a hard dependency unless current peaq documentation confirms it is available and suitable for the intended flow.

Do not claim Machine Markets compatibility for machine types or economic versions that current peaq documentation does not support.

If something needs confirmation from peaq, explicitly mark it:

```text
TODO(peaq-confirmation):
<question>
```

Do not invent an answer.

---

# 5. TYPESCRIPT AND NODE.JS

Sense is **TypeScript-first**.

Use official documentation:

TypeScript:

https://www.typescriptlang.org/docs/

Node.js:

https://nodejs.org/docs/latest/api/

npm:

https://docs.npmjs.com/

Before choosing supported Node.js versions, verify the current supported/LTS releases from the official Node.js project.

Do not blindly use an old version from this prompt.

The library must:

- be authored in TypeScript;
- compile to JavaScript;
- generate `.d.ts` declaration files;
- generate source maps;
- be usable from JavaScript;
- expose strongly typed TypeScript APIs;
- work cleanly in modern Node.js applications.

Use strict TypeScript.

At minimum:

```json
{
  "compilerOptions": {
    "strict": true
  }
}
```

Use stricter compiler options where they materially improve correctness.

Avoid unnecessary use of:

```ts
any;
```

Prefer:

```ts
unknown;
```

at untrusted boundaries and narrow it through validation.

---

# 6. JAVASCRIPT COMPATIBILITY

JavaScript developers must be able to consume Sense.

For example:

```js
import { SenseMachine } from '<package>';

const machine = new SenseMachine({
  machineRef: 'robot-001',
});
```

TypeScript users should receive full types automatically:

```ts
import { SenseMachine, defineCapability, gte, equals, fresh } from '<package>';
```

The compiled package must contain valid JavaScript.

Do not require downstream JavaScript developers to install TypeScript.

---

# 7. MODULE FORMAT

Prefer modern ESM as the canonical module format unless compatibility requirements discovered during implementation require otherwise.

Use Node.js package `exports` correctly.

If CommonJS support is added:

- configure it intentionally;
- test both ESM and CommonJS consumption;
- avoid dual-package inconsistencies;
- do not add it merely because older libraries used it.

Follow current Node.js and npm documentation.

---

# 8. PACKAGE DISTRIBUTION

The SDK must be distributable through npm.

The final package must be installable using:

```bash
npm install <package-name>
```

Do not publish a package until the final package name and namespace have been checked.

Use:

```text
package.json
tsconfig.json
src/
tests/
README.md
LICENSE
SECURITY.md
CONTRIBUTING.md
CHANGELOG.md
```

The package should expose only intentional public APIs.

Do not accidentally expose every internal module.

Use the `exports` field in `package.json`.

Example concept:

```json
{
  "exports": {
    ".": {
      "types": "./dist/index.d.ts",
      "import": "./dist/index.js"
    }
  }
}
```

The final structure must match the actual build output.

Do not copy this blindly.

---

# 9. JSON SCHEMA

Use JSON Schema Draft 2020-12.

Official specification:

https://json-schema.org/draft/2020-12

Sense context must have a language-neutral serialized representation.

This is important because future SDKs may exist in:

- Python;
- Rust;
- C++;
- Go;
- other languages.

The TypeScript implementation must not make the context format TypeScript-specific.

Every serialized context must include a schema version.

For example:

```json
{
  "schemaVersion": "1.0"
}
```

Package version and schema version are separate concepts.

---

# 10. SEMANTIC VERSIONING

Follow Semantic Versioning 2.0.0:

https://semver.org/

Use:

```text
MAJOR.MINOR.PATCH
```

Meaning:

```text
MAJOR
breaking public API changes

MINOR
backward-compatible features

PATCH
backward-compatible bug fixes
```

During early development, `0.x.y` is acceptable.

Do not release `1.0.0` until the intended public API has stabilized.

---

# 11. CONVENTIONAL COMMITS

Follow:

https://www.conventionalcommits.org/en/v1.0.0/

Every commit must follow:

```text
<type>(<scope>): <description>
```

Recommended commit types:

```text
feat
fix
docs
test
refactor
perf
build
ci
chore
```

Recommended scopes:

```text
core
schema
state
rules
events
peaq
ros2
market
docs
ci
build
security
```

Examples:

```text
build(core): initialize typescript sdk

feat(schema): add telemetry observation schema

feat(state): implement machine state store

feat(state): add telemetry freshness tracking

feat(rules): add deterministic capability evaluation

test(rules): cover stale telemetry behavior

feat(events): detect capability state transitions

feat(peaq): publish context transitions as activity events

feat(ros2): add telemetry adapter interface

docs(peaq): document activity event integration

ci(test): add sdk validation workflow
```

Bug fix:

```text
fix(state): prevent stale evidence from returning available
```

Breaking change:

```text
feat(core)!: replace capability result interface
```

Include:

```text
BREAKING CHANGE:
<explanation and migration path>
```

Never use vague commits such as:

```text
update stuff
changes
work
fix code
final
misc changes
```

Before committing:

1. inspect the diff;
2. confirm the commit has one logical purpose;
3. run relevant tests;
4. run type checking;
5. confirm no secrets are included;
6. confirm generated junk is excluded;
7. commit using Conventional Commits.

Do not rewrite shared history unless explicitly instructed.

---

# 12. WORKING METHOD

Before writing implementation code:

1. read the complete PRD;
2. inspect the entire repository;
3. inspect existing code;
4. inspect existing tests;
5. inspect git history;
6. inspect existing package configuration;
7. inspect documentation;
8. identify what is already implemented;
9. identify gaps against the PRD;
10. read the relevant official external documentation;
11. produce a concise implementation plan;
12. implement incrementally.

Do not destroy working code simply to impose another style.

Refactor only when it improves correctness, maintainability, API stability, or implementation quality.

---

# 13. ARCHITECTURE

Maintain strict separation of concerns.

Core:

```text
TelemetryObservation
        ↓
Validation
        ↓
NormalizedState
        ↓
FreshnessEngine
        ↓
CapabilityRules
        ↓
ConstraintEvaluation
        ↓
ContextSnapshot
        ↓
TransitionEngine
```

Adapters:

```text
Simulator ─┐
HTTP ──────┤
MQTT ──────┼──> Sense Core
ROS 2 ─────┤
OEM API ───┘
```

peaq:

```text
Sense Core
    ↓
peaq integration
    ↓
official peaq SDK
```

The core must not directly depend on:

- ROS 2;
- peaq;
- blockchain infrastructure;
- a specific OEM;
- cloud infrastructure;
- a database.

---

# 14. RECOMMENDED PROJECT STRUCTURE

Prefer a structure that keeps external integrations outside the smallest core.

Example:

```text
sense/
├── package.json
├── package-lock.json
├── tsconfig.json
├── README.md
├── LICENSE
├── SECURITY.md
├── CONTRIBUTING.md
├── CHANGELOG.md
│
├── schemas/
│   └── context-1.0.schema.json
│
├── src/
│   ├── index.ts
│   ├── model/
│   ├── schema/
│   ├── state/
│   ├── rules/
│   ├── engine/
│   ├── events/
│   ├── serialization/
│   └── errors/
│
├── integrations/
│   ├── peaq/
│   └── ros2/
│
├── examples/
│   ├── basic-machine/
│   ├── capability-evaluation/
│   └── peaq-events/
│
├── tests/
│   ├── unit/
│   ├── contract/
│   ├── integration/
│   └── e2e/
│
└── docs/
    ├── concepts/
    ├── integrations/
    ├── architecture.md
    ├── security.md
    └── adr/
```

This is guidance, not a requirement to force unnecessary complexity.

If npm workspaces or separate packages materially improve dependency isolation, evaluate them.

Do not introduce a monorepo purely for appearance.

---

# 15. PHASE 0 — ENGINEERING FOUNDATION

Set up professional TypeScript project infrastructure.

Required:

- TypeScript;
- strict type checking;
- npm;
- package build;
- linting;
- formatting;
- unit testing;
- CI;
- package validation;
- README;
- LICENSE;
- SECURITY.md;
- CONTRIBUTING.md;
- CHANGELOG.md;
- `.gitignore`;
- `.npmignore` or npm `files` configuration where appropriate.

Choose mature tooling.

Before choosing tools such as:

- ESLint;
- Prettier;
- Vitest;
- tsup;
- tsx;
- other build/test tools;

read their official documentation and ensure they are still maintained and suitable.

Do not add unnecessary tooling.

---

# 16. PHASE 1 — CORE DATA MODEL

Implement:

```text
TelemetryObservation
NormalizedMachineState
ContextSnapshot
timestamps
TTL
freshness
schema version
typed errors
serialization
validation
```

Conceptual observation:

```ts
interface TelemetryObservation<T = unknown> {
  path: string;
  value: T;
  observedAt: string;
  receivedAt?: string;
  source?: string;
  ttlMs?: number;
}
```

Do not treat this example as mandatory API design.

Design the final API carefully.

Required concepts:

```text
path
value
observedAt
source
ttl
```

Do not silently invent units.

Prefer explicit names:

```text
payloadKg
temperatureC
velocityMps
batteryLevelPct
```

or equivalent documented schema representation.

---

# 17. PHASE 2 — CAPABILITY ENGINE

Implement deterministic capability evaluation.

Required rule concepts:

```text
equals
notEquals
greaterThan
greaterThanOrEqual
lessThan
lessThanOrEqual
exists
inSet
fresh
ALL
ANY
NOT
```

Support:

```text
blocking constraints
degradation constraints
```

Required statuses:

```text
AVAILABLE
DEGRADED
UNAVAILABLE
UNKNOWN
```

Meaning:

### AVAILABLE

All required evidence exists, is fresh enough, and mandatory constraints pass.

### DEGRADED

Mandatory constraints permit the capability, but one or more developer-defined degradation rules are active.

### UNAVAILABLE

One or more mandatory constraints fail.

### UNKNOWN

Required evidence:

- does not exist;
- is invalid;
- cannot be interpreted;
- or is too stale.

Critical rule:

```text
UNKNOWN must never silently become AVAILABLE.
```

Every result must contain structured reasons.

---

# 18. CAPABILITY API

The public API should be easy for engineers to understand.

Conceptually:

```ts
const machine = new SenseMachine({
  machineRef: 'robot-001',
  peaqDid: 'did:peaq:...',
});

machine.observe({
  path: 'battery.levelPct',
  value: 34,
  observedAt: new Date(),
});

const result = machine.evaluate('warehouse.pick');
```

Capability definitions should remain readable.

Example:

```ts
machine.defineCapability(
  defineCapability('warehouse.pick', {
    requires: [
      equals('tool.gripper.available', true),
      equals('safety.estop', false),
      gte('battery.levelPct', 20),
      fresh('localization.pose', { maxAgeMs: 1000 }),
    ],
  }),
);
```

Prefer:

- small APIs;
- typed APIs;
- composition;
- explicit configuration;
- predictable behavior;
- immutable result objects where practical;
- meaningful errors.

Avoid:

- giant manager classes;
- implicit network calls;
- global mutable state;
- unnecessary inheritance;
- hidden side effects;
- magic strings where typed alternatives are practical;
- premature abstraction.

---

# 19. PHASE 3 — TRANSITION ENGINE

Detect meaningful capability changes.

Examples:

```text
UNKNOWN → AVAILABLE
AVAILABLE → DEGRADED
DEGRADED → UNAVAILABLE
UNAVAILABLE → AVAILABLE
```

A transition should contain enough information to explain:

```text
previous state
new state
timestamp
capability
reason
relevant evidence
```

Do not emit duplicate transitions when nothing meaningful changed.

Provide a developer subscription API.

Concept:

```ts
machine.onTransition('warehouse.pick', (transition) => {
  console.log(transition);
});
```

The final API may differ if there is a better typed design.

---

# 20. FRESHNESS

Freshness is a first-class product feature.

Distinguish:

```text
observedAt
receivedAt
evaluatedAt
```

Do not overwrite source observation time.

Where appropriate, use monotonic elapsed-time mechanisms internally for runtime duration calculations.

A developer must be able to say:

```ts
fresh('localization.pose', {
  maxAgeMs: 1000,
});
```

When evidence becomes stale, capability state must update accordingly.

---

# 21. INPUT VALIDATION

Treat telemetry as untrusted input.

Validate at boundaries.

Examples:

- malformed timestamps;
- unsupported types;
- impossible enum values;
- malformed paths;
- invalid capability definitions;
- incorrect TTL values.

Do not invent universal physical ranges where no universal range exists.

For example:

```text
battery = 120%
```

may be invalid under a developer-defined battery schema, but Sense should not assume every numeric machine field has universal semantics.

Allow domain-specific validators.

---

# 22. PEAQ INTEGRATION

peaq integration must be external to the core evaluation engine.

Use the current official JavaScript/TypeScript peaq SDK.

Before implementing each function, verify it against current official peaq documentation.

The peaq integration should cover only documented functionality.

Potential integration areas include:

```text
peaq machine identity
activity events
Machine Markets / Scale
Stream
```

Do not assume all of these are required for MVP.

---

# 23. PEAQ MACHINE IDENTITY

Sense should allow machine context to be associated with an existing peaq machine identity.

Concept:

```ts
const machine = new SenseMachine({
  machineRef: 'robot-001',
  peaqDid: 'did:peaq:...',
});
```

Do not recreate peaq onboarding as a competing identity system.

Use peaq's current supported identity representation.

---

# 24. PEAQ ACTIVITY EVENTS

Context transitions are a strong candidate for peaq activity events.

Example Sense transition:

```text
warehouse.pick

AVAILABLE
    ↓
UNAVAILABLE

reason:
LOCALIZATION_STALE
```

Sense should allow selected transitions to be explicitly published.

Concept:

```ts
await peaqPublisher.publishTransition(transition);
```

Rules:

- publishing is opt-in;
- raw telemetry is not uploaded automatically;
- use the official peaq SDK;
- respect current peaq metadata limits;
- follow peaq's documented hashing/data behavior;
- expose transaction results;
- handle failures explicitly.

Do not retry ambiguous blockchain transactions blindly.

---

# 25. MACHINE MARKETS

Sense should eventually allow its context to improve machine/service matching.

Conceptually:

```text
Sense ContextSnapshot
        ↓
peaq-compatible market context
        ↓
Machine Markets search
```

Possible useful information:

```text
current capability availability
current constraints
current state
freshness
task-related context
```

But:

Do not invent Machine Markets fields.

Only map fields supported by current official documentation.

If peaq currently does not support a machine configuration, fail clearly and document it.

---

# 26. PEAQ STREAM

Stream integration is not required for the first core MVP.

Later, Sense may expose:

```text
context snapshots
context transition streams
structured operational datasets
```

through peaq Stream.

Only implement this after reviewing current Stream documentation and after the core product is stable.

---

# 27. PEAQ VERIFY

Do not make Verify a mandatory dependency unless the current official peaq documentation says it is available and suitable.

Sense must distinguish:

```text
locally derived context

vs

blockchain-recorded event integrity

vs

hardware-level attestation
```

Never market locally calculated context as hardware-attested unless that property is actually established.

---

# 28. ROS 2

ROS 2 support should be an adapter, not part of Sense core.

Official documentation:

https://docs.ros.org/

Follow ROS 2 semantics:

```text
Topics
continuous telemetry/state

Services
short request/response

Actions
long-running behavior with feedback
```

Sense primarily consumes machine state.

Do not invent a robot-control protocol.

Important TypeScript/Node.js constraint:

Before selecting a Node.js ROS 2 library, verify:

- that it is actively maintained;
- that it supports the required ROS 2 distribution;
- its primary project documentation;
- supported Node.js versions;
- installation requirements.

Do not describe a third-party ROS 2 binding as officially maintained by ROS unless that is actually true.

If a reliable Node.js ROS 2 binding cannot satisfy the requirements:

1. keep Sense's adapter interface transport-neutral;
2. provide a documented bridge architecture;
3. do not weaken the core architecture just to force ROS 2 into Node.js.

---

# 29. ADAPTER INTERFACE

Adapters should translate external data into Sense observations.

Concept:

```ts
interface TelemetryAdapter {
  start(sink: ObservationSink): Promise<void>;
  stop(): Promise<void>;
}
```

Potential adapters:

```text
ROS 2
MQTT
HTTP
Simulator
OEM API
```

Do not make all of them part of v1.

The MVP needs at least one deterministic simulator/input path.

---

# 30. TESTING

Do not implement everything and test later.

Write tests alongside features.

Required categories:

```text
tests/unit/
tests/contract/
tests/integration/
tests/e2e/
```

Unit tests must cover:

- telemetry observations;
- validation;
- timestamps;
- state updates;
- freshness;
- stale evidence;
- missing evidence;
- rule evaluation;
- AVAILABLE;
- DEGRADED;
- UNAVAILABLE;
- UNKNOWN;
- transition detection;
- serialization;
- redaction;
- errors.

Contract tests must protect:

- public schema;
- serialized context;
- peaq event serialization;
- public SDK behavior.

Integration tests should cover:

- actual supported peaq testnet workflows;
- only when required credentials/network access exist.

End-to-end target:

```text
simulated telemetry
        ↓
Sense
        ↓
capability evaluation
        ↓
state transition
        ↓
selected peaq activity event
```

External network tests must not make local tests unreliable.

Mock external boundaries.

Do not mock the internal logic being tested.

---

# 31. JAVASCRIPT CONSUMPTION TEST

The SDK must include at least one test/example proving it works from plain JavaScript.

For example:

```js
import { SenseMachine } from '<package>';
```

This test should run against the built package rather than TypeScript source.

This verifies that TypeScript-first does not mean TypeScript-only.

---

# 32. PACKAGE INSTALLATION TEST

CI must:

1. build the npm package;
2. create the package artifact;
3. install it into a clean temporary project;
4. import the public API;
5. execute a basic example.

This catches packaging mistakes that unit tests do not.

---

# 33. CI QUALITY GATES

Every pull request must run appropriate checks.

At minimum:

```text
format check
lint
TypeScript typecheck
unit tests
contract tests
JSON Schema validation
package build
package installation smoke test
dependency/security checks
```

Integration tests requiring peaq network access should run separately.

A feature is not complete merely because it works locally on one developer machine.

---

# 34. SECURITY

Treat this SDK as software that may run alongside physical machines.

Mandatory:

- never log private keys;
- never log seed phrases;
- never commit credentials;
- never silently upload telemetry;
- validate untrusted input;
- keep key custody outside Sense core;
- support redaction;
- support publication allowlists;
- do not claim safety certification;
- capability evaluation must not directly actuate hardware;
- do not store secrets in source files;
- do not include `.env` in git.

Use:

```text
.env.example
```

only when configuration examples are necessary.

---

# 35. PRIVACY AND DATA MINIMIZATION

Raw machine telemetry should remain local by default.

Developers must choose what leaves the process.

Support concepts such as:

```text
allowlist
denylist
redaction
publishable snapshot
local-only fields
```

A peaq event should not require exposing the complete raw machine state.

---

# 36. ERROR MODEL

Use typed errors.

Potential categories:

```ts
SchemaValidationError;
UnknownCapabilityError;
MissingEvidenceError;
InvalidRuleError;
PeaqConfigurationError;
PeaqNetworkError;
UnsupportedPeaqFlowError;
SerializationError;
AdapterError;
```

Use a coherent error hierarchy.

Error messages must:

- explain what happened;
- provide actionable information;
- avoid leaking secrets.

---

# 37. DEPENDENCY DISCIPLINE

Keep core dependencies small.

Before adding a dependency ask:

1. Is this functionality already available in Node.js or TypeScript?
2. Is the package actively maintained?
3. Is it required in the core?
4. Can it live in an optional integration?
5. What is its supply-chain/security impact?
6. Does it significantly increase install size?
7. Does it introduce native compilation unnecessarily?

Keep peaq and ROS dependencies out of the smallest possible core where architecture permits.

---

# 38. SUPPLY-CHAIN SECURITY

For npm publishing:

- do not store permanent npm credentials in source;
- prefer current secure npm publishing mechanisms;
- use CI-based trusted publishing/provenance where supported;
- review dependencies;
- commit the package lockfile;
- use automated dependency monitoring if the hosting platform supports it.

Follow current npm documentation.

---

# 39. PUBLIC API DISCIPLINE

The SDK must have a clearly defined public surface.

Internal implementation should remain internal.

Avoid imports like:

```ts
import { something } from '<package>/src/internal/...';
```

Consumers should use documented exports.

Breaking public API changes require:

- SemVer handling;
- changelog entry;
- Conventional Commit breaking-change notation;
- migration documentation.

---

# 40. DOCUMENTATION

Documentation is part of the product.

Maintain at least:

```text
README.md

docs/
  quickstart.md
  concepts/
    context.md
    capabilities.md
    freshness.md
    transitions.md

  integrations/
    peaq.md
    ros2.md

  architecture.md
  security.md
```

Examples must execute.

Do not present pseudocode as working code.

Documentation must distinguish:

```text
implemented
experimental
planned
blocked
```

---

# 41. ADRs

Create architecture decision records only for meaningful decisions.

Location:

```text
docs/adr/
```

Examples:

```text
0001-typescript-first-sdk.md
0002-versioned-json-schema.md
0003-local-first-engine.md
0004-peaq-as-external-integration.md
0005-esm-package-strategy.md
```

Each ADR should contain:

```text
Context
Decision
Alternatives considered
Consequences
```

Do not create ADRs for trivial choices.

---

# 42. PERFORMANCE

The core must not require a GPU.

The hot path is:

```text
observation
    ↓
state update
    ↓
freshness
    ↓
rules
    ↓
result
```

No blockchain calls occur during this path.

Do not claim specific latency numbers before benchmarking.

Add benchmarks only when they answer a real engineering question.

---

# 43. MVP DEMO

Build one complete vertical slice before expanding the SDK.

Use a simulated machine if necessary.

Telemetry:

```text
battery.levelPct
safety.estop
localization.status
localization.pose
tool.gripper.available
payload.currentKg
payload.maxKg
```

Capability:

```text
warehouse.pick
```

Rules:

```text
battery >= configured threshold
estop == false
localization == valid
localization is fresh
gripper == available
payload <= configured maximum
```

Expected output:

```text
AVAILABLE
DEGRADED
UNAVAILABLE
UNKNOWN
```

with structured reasons.

---

# 44. MVP EXAMPLE

Initial state:

```text
battery: 78%
estop: false
localization: valid
gripper: available
payload: 8kg
maximum payload: 20kg
```

Sense:

```text
warehouse.pick = AVAILABLE
```

Then:

```text
localization data becomes stale
```

Sense:

```text
warehouse.pick = UNKNOWN

reason:
LOCALIZATION_STALE
```

Then:

```text
localization restored
payload = 21kg
```

Sense:

```text
warehouse.pick = UNAVAILABLE

reason:
PAYLOAD_LIMIT_EXCEEDED
```

A selected transition can then optionally be published to peaq.

---

# 45. DEVELOPMENT PHASES

## Phase 0

Engineering foundation.

Deliver:

```text
TypeScript project
package configuration
strict tsconfig
lint
format
test
build
CI
docs skeleton
```

Commit example:

```text
build(core): initialize typescript sdk
```

---

## Phase 1

Core models.

Deliver:

```text
TelemetryObservation
state representation
timestamps
freshness
ContextSnapshot
schema validation
typed errors
```

---

## Phase 2

Capability engine.

Deliver:

```text
rules
constraint evaluation
statuses
explanations
```

---

## Phase 3

Transition engine.

Deliver:

```text
state-change detection
subscriptions
transition serialization
```

---

## Phase 4

peaq integration.

Deliver only against current official documentation:

```text
identity association
activity event serialization
activity event publishing
network handling
testnet verification
```

---

## Phase 5

External machine adapters.

Start with the simplest reliable integration.

ROS 2 can be implemented once the Node.js/TypeScript integration approach has been validated.

---

## Phase 6

Machine Markets integration.

Only implement currently supported peaq behavior.

---

## Phase 7

Stream integration.

Optional and only after the core SDK is stable.

---

# 46. WHEN BLOCKED

If functionality requires:

- credentials;
- funds;
- private access;
- unreleased peaq functionality;
- unavailable hardware;
- peaq confirmation;
- unsupported Node.js integration;

do not fake the result.

Document:

```text
BLOCKED:
<what is blocked>

REASON:
<why>

OFFICIAL SOURCE:
<link>

REQUIRED:
<what is needed>
```

Then continue implementing everything that can be implemented correctly.

---

# 47. DEFINITION OF DONE

A feature is complete only when:

- implementation exists;
- TypeScript types are correct;
- tests exist;
- tests pass;
- lint passes;
- typecheck passes;
- documentation exists;
- public API is intentional;
- external behavior matches official documentation;
- error behavior exists;
- no credentials exist in the diff;
- package builds;
- JavaScript output works;
- appropriate Conventional Commit exists.

---

# 48. FINAL ENGINEERING VALIDATION

Before declaring the MVP complete:

Run:

```text
clean install

typecheck

lint

format validation

unit tests

contract tests

package build

clean package installation test

JavaScript consumption example

TypeScript consumption example
```

Run network integration tests separately where possible.

Do not claim a peaq integration is verified unless it was actually executed successfully.

---

# 49. FINAL MVP FLOW

The final demonstration should show:

```text
Machine / Simulator
        ↓
Raw telemetry
        ↓
Sense
        ↓
Normalized physical state
        ↓
Freshness
        ↓
Capability evaluation
        ↓
AVAILABLE / DEGRADED / UNAVAILABLE / UNKNOWN
        ↓
Structured explanation
        ↓
State transition
        ↓
Optional peaq activity event
```

The entire flow through capability evaluation must work when the machine has no internet connection.

---

# 50. FINAL OUTPUT FROM THE AGENT

At completion, provide a concise engineering report containing:

## Implemented

What actually exists.

## Architecture

How the core and integrations are separated.

## Public API

The developer-facing API.

## Tests

What was tested and results.

## peaq

Which peaq operations were actually verified.

## Unverified / blocked

Anything that could not be tested.

## Repository structure

Final relevant file tree.

## Commit history

List the meaningful Conventional Commits.

## Developer commands

Exact commands for:

```text
install
development
typecheck
lint
test
build
run example
```

## JavaScript usage

Show a working JavaScript example.

## TypeScript usage

Show a working TypeScript example.

---

# 51. EXECUTION INSTRUCTION

Start now.

First:

1. read the PRD completely;
2. inspect the repository;
3. inspect git history;
4. inspect current configuration;
5. read current official peaq documentation;
6. read official documentation for every external technology selected;
7. identify PRD/documentation conflicts;
8. produce a concise implementation plan;
9. begin Phase 0;
10. build one complete vertical slice;
11. test continuously;
12. commit logical milestones using Conventional Commits;
13. continue until all implementable MVP acceptance criteria are satisfied.

Do not stop after scaffolding.

Do not return only a plan.

Do not replace real implementation with placeholders.

Do not claim tests passed without running them.

Do not claim integrations work without verifying them.

Do not hallucinate unsupported peaq functionality.

Build **Sense** as an SDK engineers would be comfortable depending on in a real machine software stack.
Let us start this again
