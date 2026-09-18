# Contributing to Sense

Sense is a local-first SDK for converting physical machine telemetry into current capability context.

Changes should preserve that boundary.

## Development setup

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense

python -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

For peaq work:

```bash
pip install -e packages/Sense-peaq
```

## Before changing an integration

Use the current official documentation.

For peaq:

https://docs.peaq.xyz/

For ROS 2:

https://docs.ros.org/

Do not invent an external API because a desired operation sounds plausible.

If upstream behavior is unavailable or unclear, keep the adapter boundary explicit and document the limitation.

## Quality checks

Run:

```bash
ruff check src/ packages/
ruff format --check src/ packages/
mypy -p sense_ai

pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v

pip install -e packages/Sense-peaq
pytest tests/e2e/ -v

python -m build
```

## Tests

Add tests with behavior changes.

Use:

- `tests/unit/` for deterministic core behavior;
- `tests/contract/` for schema/public serialization;
- `tests/integration/` for multi-component local flows;
- `tests/e2e/` for full adapter boundaries.

Network-dependent peaq tests must not make normal PR checks flaky.

## Conventional Commits

Every commit must use Conventional Commits:

```text
<type>(<scope>): <description>
```

Examples:

```text
feat(rules): add numeric range constraint
fix(core): re-evaluate snapshots after freshness expiry
fix(peaq): publish transitions as activity events
test(schema): cover structured telemetry values
docs(ros2): clarify qos configuration
ci(test): add package installation smoke test
```

Common types:

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

Use `!` and a `BREAKING CHANGE:` footer for breaking public API changes.

Keep each commit focused on one logical purpose.

## Pull requests

A PR should explain:

- what changed;
- why;
- public API impact;
- tests added/updated;
- external documentation used for integrations;
- anything intentionally left unverified.

Do not claim a peaq operation was live-tested unless it was actually executed against a configured peaq environment.

## Product boundaries

Avoid adding unrelated platform features to the core.

Sense should remain focused on:

```text
telemetry
→ physical context
→ freshness
→ current capabilities/constraints
→ explainable transitions
```

Network, blockchain, ROS 2, OEM and simulator support should stay behind adapters where practical.

## Security

Read [SECURITY.md](SECURITY.md) before changing telemetry publication, credentials, network integrations, or robot-facing code.
