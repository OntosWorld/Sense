# sense-peaq

Official peaqOS integration for Sense 0.3.x.

This package publishes selected Sense capability transitions through the official
peaqOS Python SDK and delegates Machine Markets operations to
`PeaqosClient.orchestration`.

It does not reimplement peaq identity, Events, signing, or market schemas.

## Install

```bash
pip install sense-peaq
```

From this repository:

```bash
pip install -e packages/Sense-peaq
```

Requirements:

- Python 3.10+
- `sense-ai>=0.3.0`
- `peaq-os-sdk>=0.8.0`

## Activity Events

```python
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqEventPublisher

client = PeaqosClient.from_env()
publisher = PeaqEventPublisher(client, machine_id=42)

transition = machine.last_transition("warehouse.pick")
if transition is not None:
    receipt = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
    )
```

Sense passes the event to the official `submit_event()` API.

Observed reason values are redacted by default. Use
`include_observed_values=True` only when disclosure is intentional.

## Provenance

Default Sense context is self-reported/off-chain:

```text
trust_level = 0
source_chain_id = 0
source_tx_hash = None
```

On-chain-verifiable context requires real provenance:

```python
from sense_peaq import EventProvenance

provenance = EventProvenance.onchain(
    source_chain_id=8453,
    source_tx_hash="0x...",
)

publisher.publish_transition(
    transition,
    provenance=provenance,
)
```

Trust level 1 is rejected without a source transaction hash.

Sense currently rejects trust level 2 rather than claiming hardware attestation
without an attested hardware proof.

## Machine Markets

```python
from sense_peaq import MachineMarketsAdapter

markets = MachineMarketsAdapter(client)

machines = markets.list_machines(limit=20)
services = markets.list_market_services(limit=20)
service = markets.get_market_service("service-id")
```

Search calls use request types from the current `peaq-os-sdk`:

```python
result = markets.search_market(request, pairing_token)
status = markets.get_market_search(result.search_id)
```

Sense does not define alternate market fields.

## Runtime physical capability gating

Use current Sense context before accepting/selecting a machine:

```python
from sense_peaq import check_market_eligibility

eligibility = check_market_eligibility(
    machine.snapshot(),
    ["warehouse.pick"],
)

if eligibility.eligible:
    ...
```

For arbitrary market result objects:

```python
from sense_peaq import filter_market_candidates

selected = filter_market_candidates(
    candidates,
    snapshots_by_machine=snapshots,
    required_capabilities=["warehouse.pick"],
    machine_ref=lambda candidate: candidate.machine_ref,
)
```

The caller supplies the machine-reference extractor so Sense does not guess
fields on peaq SDK response models.

## Runtime context

```python
from sense_peaq import to_market_context

context = to_market_context(machine.snapshot())
```

This output is application/agent context, not an undocumented peaq schema.

## Configuration

Use the official peaqOS environment configuration:

https://docs.peaq.xyz/peaqos/install

Machine Markets orchestration currently uses the official orchestration client
surface documented by peaq:

https://docs.peaq.xyz/peaqos/sdk-reference/orchestration-py

## Testing

Deterministic adapter contract tests:

```bash
pip install -e ".[dev]"
pip install -e packages/Sense-peaq
pytest tests/e2e/test_peaq_integration.py -v
```

Real network verification is opt-in:

```bash
export SENSE_RUN_LIVE_PEAQ=1
export SENSE_PEAQ_MACHINE_ID=<machine id>
pytest tests/live/test_peaq_activity_event.py -v -s
```

See [live test instructions](../../tests/live/README.md).

A mocked adapter test is not presented as proof of a live transaction.

## Security

- publication is opt-in;
- raw snapshot observations are excluded by default;
- reason values are redacted by default;
- Sense does not manage private keys;
- trust level cannot be upgraded without the provenance required by the adapter;
- hardware-signed trust is intentionally unsupported until real attestation is integrated.

## License

Apache-2.0.
