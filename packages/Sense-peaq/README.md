# sense-peaq

Official peaqOS integration for Sense 0.3.x.

This package publishes selected Sense capability transitions through the official
peaqOS Python SDK and delegates Machine Markets operations to
`PeaqosClient.orchestration`.

It does not reimplement peaq identity, Events, signing, or market schemas.

## Install

The Sense packages are not yet published on PyPI. From the repository root:

```bash
pip install -e .
pip install -e packages/Sense-peaq
```

Requirements:

- Python 3.10+
- `sense-ai>=0.3.0`
- `peaq-os-sdk>=0.8.0`

## One-command live verification

For an already configured peaq wallet and machine ID, the complete live check is:

```bash
sense-peaq verify-live
```

The command:

- loads the user's normal peaqOS SDK environment;
- creates `PeaqosClient.from_env()`;
- displays the signer address, RPC, deployment, and machine ID;
- builds and validates a real Sense capability transition locally;
- asks for confirmation before spending gas;
- submits one real peaq Activity Event;
- prints the transaction hash and data hash.

The private key is never accepted as a Sense CLI argument and is never printed by
Sense. Wallet configuration remains owned by the official peaqOS SDK.

For Agung, Sense fills missing public contract addresses from peaq's official
[`peaqos.json`](https://github.com/peaqnetwork/peaq-evm-smart-contracts/blob/dev/addresses/peaqos.json)
deployment record. Explicit environment values are never overwritten. Secrets
such as `PEAQOS_PRIVATE_KEY` are never defaulted.

Pass a machine ID directly when desired:

```bash
sense-peaq verify-live --machine-id 42
```

For automated/dev environments where transaction approval is already handled:

```bash
sense-peaq verify-live --machine-id 42 --yes
```

From a fresh checkout, the repository helper automates setup, local wallet
creation, funding verification, wallet-free checks, and the same live command:

```bash
git clone https://github.com/OntosWorld/Sense.git \
  && cd Sense \
  && bash scripts/peaq-live-test.sh
```

## Activity Events

```python
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqEventPublisher, apply_official_network_defaults

apply_official_network_defaults()
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

The built-in Agung profile supplies these public values when the configured RPC
URL contains `agung`, or when `TOKENOMICS_DEPLOYMENT_ID=agung-2026-08-28`:

```text
IDENTITY_REGISTRY_ADDRESS=0x9E9463a65c7B74623b3b6Cdc39F71be7274e5971
IDENTITY_STAKING_ADDRESS=0x55f336714aDb0749DbFE33b057a1702405564E3d
EVENT_REGISTRY_ADDRESS=0x98De5e22c46e17A56235C3589586375B09F7c53D
MACHINE_NFT_ADDRESS=0xB41C2A4f1c19b6B06beaAce0F5CD8439e77C4b1c
DID_REGISTRY_ADDRESS=0x0000000000000000000000000000000000000800
BATCH_PRECOMPILE_ADDRESS=0x0000000000000000000000000000000000000805
```

The live CLI verifies that the connected chain ID is `9990` before it asks for
transaction confirmation. Other networks receive no inferred defaults.

The Tokenomics EventRegistry is resolved from the machine-data contracts
registered by the SDK-approved `agung-2026-08-28` InfoDesk. This intentionally
differs from the legacy EventRegistry still present in `peaqos.json`. Sense also
clamps event timestamps to the latest EVM block, preventing small workstation /
validator clock differences from causing `FutureTimestamp` reverts.

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
