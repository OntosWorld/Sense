# sense-peaq

Official peaqOS integration for Sense.

This package connects **selected Sense capability context** to peaq. It does not reimplement peaq identity, Events, Machine Markets, signing, or transaction logic.

## Install

From the Sense repository:

```bash
pip install -e packages/Sense-peaq
```

Requirements:

- Python 3.10+
- `sense-ai>=0.2.0`
- `peaq-os-sdk>=0.4.0`

Current peaq docs:

- https://docs.peaq.xyz/peaqos/install
- https://docs.peaq.xyz/peaqos/concepts/events
- https://docs.peaq.xyz/peaqos/concepts/machine-markets
- https://docs.peaq.xyz/peaqos/sdk-reference/sdk-python
- https://docs.peaq.xyz/peaqos/sdk-reference/orchestration-py

## What this adapter does

```text
machine telemetry
      ↓
Sense
      ↓
capability transition
      ↓
PeaqEventPublisher
      ↓
PeaqosClient.submit_event()
      ↓
peaq Activity Event
```

For Machine Markets:

```text
Sense ContextSnapshot
      ↓
runtime capability context
      ↓
machine agent/application
      ↓
PeaqosClient.orchestration
```

## Configure peaqOS

Follow peaq's official environment-variable documentation.

Typical setup:

```python
from dotenv import load_dotenv
from peaq_os_sdk import PeaqosClient

load_dotenv()

client = PeaqosClient.from_env()
```

Sense does not read or store the private key itself. Key handling belongs to the configured peaqOS client.

## Publish a capability transition

```python
from sense_peaq import PeaqEventPublisher

publisher = PeaqEventPublisher(
    client,
    machine_id=42,
)

transition = machine.last_transition("warehouse.pick")

if transition is not None:
    result = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
    )

    print(result.tx_hash)
    print(result.data_hash_hex)
```

The publisher calls the official peaqOS `submit_event()` method with an **Activity Event**.

### Default provenance

For ordinary locally derived Sense context:

```text
trust_level = 0
source_chain_id = 0
```

This means self-reported/off-chain data under peaq's event model.

Do not set trust level `1` or `2` unless the event really satisfies peaq's documented on-chain or hardware-signed provenance requirements.

## Raw data and hashing

The official peaqOS SDK handles the Activity Event's `raw_data` hashing and transaction submission.

Sense passes a compact transition payload such as:

```json
{
  "type": "sense.capability_transition",
  "transition": {
    "capability": "warehouse.pick",
    "previous": "AVAILABLE",
    "current": "UNAVAILABLE"
  }
}
```

The project can keep detailed raw telemetry local. Use `publishable_view()` before providing a snapshot; it contains no raw observations unless the developer explicitly allowlists them.

## Metadata

Sense adds small metadata describing the producer and schema.

peaq currently documents a 4096-byte metadata limit. The adapter rejects larger metadata rather than silently truncating it.

## Machine Markets / Scale

Sense does **not** expose a custom `/listings` endpoint and does not create its own marketplace model.

Use:

```python
from sense_peaq import MachineMarketsAdapter

markets = MachineMarketsAdapter(client)

machines = markets.list_machines(limit=20)
services = markets.list_market_services(limit=20)
```

These calls delegate directly to:

```python
client.orchestration
```

For Scale/Machine Markets, configure:

```text
PEAQOS_ORCHESTRATION_URL=https://orchestration.peaq.xyz
```

before creating `PeaqosClient`.

If your orchestrator requires API authentication, follow peaq's current documentation for `PEAQOS_API_KEY`.

## Search Machine Markets

Sense deliberately does not clone peaq's request models.

Construct the search request with the types exported by the current `peaq-os-sdk`, then pass it through:

```python
result = markets.search_market(
    request,
    pairing_token,
)
```

This keeps Sense compatible with peaq's current orchestration contract rather than freezing a duplicate schema inside this repository.

## Runtime Sense context

```python
from sense_peaq import to_market_context

context = to_market_context(machine.snapshot())
```

Example shape:

```json
{
  "sense": {
    "schema_version": "1.0",
    "machine_ref": "robot-001",
    "capabilities": {
      "warehouse.pick": {
        "status": "UNAVAILABLE",
        "unknown_paths": [],
        "reasons": []
      }
    },
    "currently_usable_capabilities": []
  }
}
```

This is application/agent context. It is **not** presented as an undocumented peaq Machine Markets field.

## Errors

peaq adapter failures are exposed through Sense typed errors:

```python
from sense_ai import PeaqConfigurationError, PeaqNetworkError
```

- `PeaqConfigurationError`: invalid local adapter configuration.
- `PeaqNetworkError`: peaq SDK/orchestration call failed.

## Security

- Publishing is opt-in.
- Sense does not automatically upload telemetry.
- The adapter does not log private keys or seed phrases.
- Use `ContextSnapshot.publishable_view()` for external data.
- Trust level defaults to self-reported rather than overstating provenance.

## Testing

```bash
pip install -e ".[dev]"
pip install -e packages/Sense-peaq

pytest tests/e2e/test_peaq_integration.py -v
```

The normal e2e suite mocks the network boundary. A successful mock test proves the Sense adapter contract, not live-chain connectivity.

Live peaq verification should be run separately with a funded/configured test environment.

## License

Apache-2.0.
