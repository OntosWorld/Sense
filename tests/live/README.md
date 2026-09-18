# Live integration tests

Live tests are intentionally separate from normal CI because they require
network access, credentials and may spend real gas.

## peaq Activity Event

The repository includes a protected manual workflow:

```text
.github/workflows/live-peaq.yml
```

It submits one real self-reported Sense Activity Event through the official
`PeaqosClient.from_env()` path.

### GitHub Actions setup

Create a GitHub Environment named:

```text
peaq-live
```

Add one environment secret named:

```text
PEAQOS_ENV_FILE
```

Its value should be the complete dotenv configuration required by the installed
`peaq-os-sdk` version, for example the RPC URL, funded private key and any
contract/deployment configuration required by `PeaqosClient.from_env()`.

Do **not** commit that file or the private key.

Then run **Live peaq verification** from GitHub Actions and provide:

- an existing decimal peaq machine ID;
- the explicit gas-spend confirmation checkbox.

The workflow will not run the transaction unless the confirmation is true. It
uses the protected `peaq-live` environment, writes the dotenv secret only for
the job, and removes it afterward.

### Local run

Configure the official peaqOS environment first, then set:

```bash
export SENSE_RUN_LIVE_PEAQ=1
export SENSE_PEAQ_MACHINE_ID=<decimal machine id>
```

Install and run:

```bash
pip install -e .
pip install -e packages/Sense-peaq
pip install python-dotenv

pytest tests/live/test_peaq_activity_event.py -v -s
```

This is a real transaction. Use a funded test/dev environment unless you
intentionally want to write to another network.
