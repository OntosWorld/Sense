# Example 04 — peaqOS integration

This example shows the integration boundary Sense is designed for:

```text
machine telemetry
    ↓
Sense capability evaluation
    ↓
meaningful capability transition
    ↓
peaq Activity Event
```

Sense does **not** create a competing machine identity, marketplace, or listing
registry. The adapter uses the official `peaq-os-sdk` surface.

## Install

From the repository root:

```bash
pip install -e .
pip install -e packages/Sense-peaq
```

## Run the offline example

```bash
PYTHONPATH=src:packages/Sense-peaq/src python examples/04_peaq/evaluate.py
```

The included fake client prints the exact arguments that would be passed to
`PeaqosClient.submit_event()`.

## Real peaq client

Configure the official SDK and pass the client into Sense:

```python
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqContextPublisher

client = PeaqosClient.from_env()
publisher = PeaqContextPublisher(client, machine_id=123)

publisher.publish_transition(
    machine.last_transition("delivery.ready"),
    machine_ref=machine.machine_ref,
)
```

Sense publishes Activity Events with `TRUST_SELF_REPORTED` by default. It does
not claim on-chain-verifiable or hardware-signed provenance unless the caller
explicitly supplies a different trust level backed by the required evidence.

## Machine Markets

`MachineMarketsAdapter` delegates to the official
`client.orchestration` namespace. Sense does not invent listing or bidding
endpoints. `to_market_context(snapshot)` only produces local runtime capability
context that applications can use alongside peaq market search and service
results.
