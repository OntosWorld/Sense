# sense-peaq

peaq network adapter for the Sense AI evaluation framework.

Provides:

- **`PeaqContextPublisher`** — submits capability snapshots to peaq as signed DID documents via the peaqOS RPC interface.
- **`MachineMarketsAdapter`** — queries and bids on machine capability listings via peaq DID documents.

## Installation

```bash
pip install sense-peaq
```

Requires the `sense-ai` core SDK and a configured peaqOS RPC endpoint. The adapter does not handle key custody — supply an already-configured peaq client.

## PeaqContextPublisher

Publishes a `ContextSnapshot` to the peaq network as a signed DID document update.

```python
from datetime import datetime, timezone
from sense_ai import ContextMachine, TelemetryObservation, capability, gte
from sense_peaq import PeaqContextPublisher

# Set up the machine
machine = ContextMachine(
    machine_ref="drone-001",
    peaq_did="did:peaq:0x1234...abcd",
)

machine.define_capability(
    capability(
        "delivery.ready",
        requires=[gte("battery.level_pct", 30)],
    )
)

machine.observe("battery.level_pct", 72)

# Publish the current snapshot to peaq
publisher = PeaqContextPublisher(
    rpc_endpoint="https://api.peaq.network",
    peaq_client=my_peaq_client,  # pre-configured peaqOS client instance
)

result = publisher.publish(machine.snapshot())
print(result.tx_hash)   # on-chain transaction hash
print(result.block_num)  # block number when confirmed
```

### Key behaviour

- Publishing is **always opt-in** — raw telemetry is never uploaded automatically.
- The SDK submits a signed DID document update via the peaq RPC interface.
- Submission waits for transaction confirmation (configurable timeout).
- Raises `PeaqNetworkError` if the RPC call fails or the transaction is rejected.
- Raises `PeaqConfigurationError` if the peaq DID is not set on the machine.

## MachineMarketsAdapter

Queries machine capability listings from the peaq DID document registry and bids on matching listings.

```python
from sense_peaq import MachineMarketsAdapter

adapter = MachineMarketsAdapter(
    rpc_endpoint="https://api.peaq.network",
    peaq_client=my_peaq_client,
)

# Find all listings that match a capability query
listings = adapter.query_listings(
    capability="warehouse.pick",
    min_status="AVAILABLE",
)

for listing in listings:
    print(listing.machine_did)
    print(listing.capability)
    print(listing.last_evaluated)

# Bid on a listing
bid = adapter.create_bid(
    listing_id=listings[0].listing_id,
    price_micro_peaq=1_000_000,
)
receipt = adapter.submit_bid(bid)
print(receipt.tx_hash)
```

### MachineListing

Each listing returned by `query_listings` is a `MachineListing` object:

| Field | Type | Description |
|-------|------|-------------|
| `listing_id` | `str` | Unique listing identifier on peaq |
| `machine_did` | `str` | peaq DID of the machine |
| `capability` | `str` | Capability name (e.g. `warehouse.pick`) |
| `status` | `CapabilityStatus` | Last known capability status |
| `last_evaluated` | `datetime` | When the snapshot was produced |
| `metadata` | `dict` | Additional on-chain metadata |

### Creating a listing

Expose your machine's snapshot as a DID document listing:

```python
listing = MachineListing.from_dict({
    "listing_id": "0xabcd...",
    "machine_did": "did:peaq:0x1234...abcd",
    "capability": "warehouse.pick",
    "status": "AVAILABLE",
    "last_evaluated": "2025-01-15T10:00:00Z",
    "metadata": {"region": "eu-west-1"},
})

adapter.register_listing(listing)
```

## Error handling

All peaq-specific errors inherit from `sense_ai.PeaqConfigurationError` or `sense_ai.PeaqNetworkError`:

```python
from sense_ai import PeaqNetworkError, PeaqConfigurationError

try:
    result = publisher.publish(snapshot)
except PeaqConfigurationError as e:
    print(f"Configuration error: {e}")  # DID not set, endpoint not configured
except PeaqNetworkError as e:
    print(f"Network error: {e}")         # RPC failure, tx rejected
```

## Security

- **No key custody** — the adapter never handles private keys. Supply a read-only or appropriately-scoped peaq client.
- **Opt-in only** — telemetry is never published automatically.
- **Typed errors** — all failure modes produce typed `SenseError` subclasses.

## API reference

### PeaqContextPublisher

```python
class PeaqContextPublisher:
    def __init__(
        self,
        rpc_endpoint: str,
        peaq_client: Any,          # pre-configured peaqOS client
        tx_timeout_s: float = 30,  # seconds to wait for tx confirmation
    ) -> None: ...

    def publish(self, snapshot: ContextSnapshot) -> PublishResult:
        """
        Submit snapshot to peaq as a signed DID document update.

        Raises:
            PeaqConfigurationError: peaq DID not set on the machine.
            PeaqNetworkError: RPC failure or transaction rejected.
        Returns:
            PublishResult with tx_hash and block_num on success.
        """
```

### MachineMarketsAdapter

```python
class MachineMarketsAdapter:
    def __init__(
        self,
        rpc_endpoint: str,
        peaq_client: Any,
    ) -> None: ...

    def query_listings(
        self,
        capability: str | None = None,
        min_status: str | None = None,
    ) -> list[MachineListing]: ...

    def register_listing(self, listing: MachineListing) -> None: ...

    def create_bid(
        self,
        listing_id: str,
        price_micro_peaq: int,
    ) -> Bid: ...

    def submit_bid(self, bid: Bid) -> BidReceipt: ...
```

## License

Apache-2.0
