# Contributing to Sense

Sense is a local-first SDK for converting raw physical-machine telemetry into
validated current capability context.

Changes should preserve that boundary.

## Setup

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Adapter development:

```bash
pip install -e packages/Sense-peaq
pip install -e packages/Sense-ros2
pip install -e packages/Sense-mqtt
pip install -e packages/Sense-http
```

## Architecture

Core:

```text
raw telemetry
→ validation
→ normalization
→ canonical observations
→ freshness
→ capability evaluation
→ reasons / transitions
```

Network, ROS, OEM, and blockchain-specific code belongs behind adapter
boundaries.

## External APIs

Verify current upstream documentation before changing an integration.

- peaq: https://docs.peaq.xyz/
- ROS 2: https://docs.ros.org/

Do not invent methods, fields, market schemas, or provenance behavior.

## Quality checks

```bash
ruff check src/ packages/
ruff format --check src/ packages/
mypy -p sense_ai

pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v

pip install -e packages/Sense-peaq
pytest tests/e2e/ -v

pytest packages/Sense-ros2/tests -v
pytest packages/Sense-mqtt/tests -v
pytest packages/Sense-http/tests -v

python -m build
```

Live external tests are separate and opt-in.

## Test layers

- `tests/unit/`: deterministic core semantics;
- `tests/contract/`: serialized/schema contracts;
- `tests/integration/`: local component integration;
- `tests/e2e/`: complete SDK/adapter flows using controlled boundaries;
- `tests/live/`: explicit real-network verification;
- adapter-local `tests/`: transport contracts.

## Invariants

Do not weaken:

- `UNKNOWN` is never `AVAILABLE`;
- missing, stale, invalid mandatory evidence → `UNKNOWN`;
- concrete valid failure → `UNAVAILABLE`;
- raw telemetry remains local by default;
- adapter failure does not corrupt local state;
- Sense does not perform robot actuation.

## Conventional Commits

```text
<type>(<scope>): <description>
```

Examples:

```text
feat(telemetry): add unit normalization
fix(rules): preserve invalid evidence as unknown
feat(ros2): map battery state into canonical telemetry
fix(peaq): require source proof for trust level one
test(adapters): cover mqtt ingestion
docs(readme): document raw telemetry pipeline
ci(release): build first-party packages
```

Use `!` and a `BREAKING CHANGE:` footer for breaking public APIs.

## Pull requests

Describe:

- behavior change;
- reason;
- public contract impact;
- tests;
- upstream docs used for external integrations;
- anything not live-verified.

Never describe a mocked peaq test as a live transaction.

## Release changes

Keep first-party package versions aligned and update:

- `CHANGELOG.md`;
- compatibility documentation;
- public READMEs;
- examples affected by the API.

## Security

Read [SECURITY.md](SECURITY.md) before changing transport credentials, telemetry
publication, robot-facing behavior, or external transaction logic.
