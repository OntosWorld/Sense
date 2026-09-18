# Contributing to Sense

Thank you for contributing to Sense.

## Development setup

```bash
git clone https://github.com/OntosWorld/Sense.git
cd Sense
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional adapters:

```bash
pip install -e packages/Sense-peaq
pip install -e packages/Sense-ros2
```

## Quality checks

Run the same checks expected in CI:

```bash
ruff format --check src tests
ruff check src tests
mypy src
pytest tests/unit/ -v
pytest tests/contract/ -v
pytest tests/integration/ -v
pytest tests/e2e/test_pipeline.py -v
python -m build
```

The build job also installs the generated wheel and imports the public API.

## Code style

- Python 3.10+.
- Keep the core local-first and transport-neutral.
- Do not add peaq, ROS 2, cloud, or OEM dependencies to the core package unless the architecture genuinely requires them.
- Prefer typed, explicit public APIs.
- Treat telemetry as untrusted input.
- Keep network or blockchain operations outside the capability-evaluation hot path.
- Do not silently publish raw telemetry.

Formatting and linting use Ruff. Static typing uses mypy in strict mode.

## Tests

New behavior should include the smallest relevant test layer:

- `tests/unit/` — deterministic core behavior;
- `tests/contract/` — serialized schema/API contracts;
- `tests/integration/` — multi-component local flows;
- `tests/e2e/` — complete pipelines and optional adapter contracts.

Live peaq tests must remain opt-in and must not make ordinary pull requests dependent on network availability or funded wallets.

## peaq integration

Use the current official `peaq-os-sdk` documentation as the source of truth.

Do not invent RPC methods, REST endpoints, DID document extensions, market listing schemas, or transaction behavior.

Sense's peaq boundary is:

```text
Sense physical context
    ↓
official peaqOS SDK
    ↓
Activity Events / orchestration / supported peaq functions
```

If current peaq documentation does not support a flow, document it as unsupported or pending instead of creating a speculative API.

## Conventional Commits

All commits must follow [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):

```text
<type>(<scope>): <description>
```

Types:

```text
feat fix docs test refactor perf build ci chore
```

Common scopes:

```text
core schema rules events peaq ros2 market docs ci build security
```

Examples:

```text
feat(rules): add deterministic capability constraint
fix(core): reevaluate stale observations on snapshot
feat(peaq): publish capability transitions as activity events
test(schema): cover context round-trip
docs(readme): clarify machine markets boundary
ci(test): add package installation smoke test
```

Use `!` and a `BREAKING CHANGE:` footer for breaking public API changes.

## Pull requests

1. Create a focused branch.
2. Make one logical change at a time.
3. Add or update tests.
4. Update documentation for public behavior.
5. Run the quality checks.
6. Review the full diff for generated files, secrets, and unrelated changes.
7. Open a pull request with the behavior change and validation steps.

## Generated files

Do not commit:

```text
__pycache__/
*.pyc
.pytest_cache/
.coverage
*.egg-info/
dist/
build/
```

## Security

Never commit private keys, seed phrases, wallet exports, credentials, or sensitive machine telemetry.

See [SECURITY.md](SECURITY.md).

## License

Contributions are licensed under Apache-2.0.
