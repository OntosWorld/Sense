# Example 04 — peaqOS Integration

This example demonstrates publishing a capability snapshot to the peaq network as a signed DID document, and querying the Machine Markets listing registry.

> Uses a mock peaq client by default. Set `RPC_ENDPOINT` and supply a real peaqOS client to exercise on-chain publishing.

**Run from the repo root:**

```bash
PYTHONPATH=src:packages/Sense-peaq/src python examples/04_peaq/evaluate.py
```

**With a real endpoint (requires a configured peaqOS client):**

```bash
RPC_ENDPOINT=https://api.peaq.network \
PYTHONPATH=src:packages/Sense-peaq/src python examples/04_peaq/evaluate.py
```

## What it does

1. Builds a `ContextMachine` with a `delivery.ready` capability and ingests telemetry
2. Creates a `PeaqContextPublisher` and submits the snapshot as a signed DID document update
3. Queries the Machine Markets registry for `warehouse.pick` listings
4. Displays transaction hashes (real or mock) and listing details

## Key concepts

### Publishing to peaq

```python
from sense_peaq import PeaqContextPublisher

publisher = PeaqContextPublisher(
    rpc_endpoint="https://api.peaq.network",
    peaq_client=my_peaq_client,   # pre-configured peaqOS client
    tx_timeout_s=30,
)

result = publisher.publish(machine.snapshot())
print(result.tx_hash)    # on-chain transaction hash
print(result.block_num)  # block number on confirmation
```

### Error handling

```python
from sense_ai import PeaqConfigurationError, PeaqNetworkError

try:
    result = publisher.publish(snapshot)
except PeaqConfigurationError:
    print("peaq DID not set on the machine — set machine.peaq_did = 'did:peaq:...'")
except PeaqNetworkError as e:
    print(f"RPC or transaction error: {e}")
```

### Querying Machine Markets

```python
from sense_peaq import MachineMarketsAdapter

markets = MachineMarketsAdapter(rpc_endpoint=rpc_endpoint, peaq_client=peaq_client)

# Find listings by capability and minimum status
listings = markets.query_listings(capability="warehouse.pick", min_status="AVAILABLE")

for listing in listings:
    print(listing.machine_did, listing.status, listing.last_evaluated)
```

### Security notes

- Publishing is always opt-in — the SDK never uploads telemetry automatically
- The adapter does not handle private keys — supply a scoped peaqOS client
- Raw telemetry stays local; only the structured `ContextSnapshot` is submitted
