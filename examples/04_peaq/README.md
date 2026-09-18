# Example 04 — peaq integration

This example demonstrates the supported Sense → peaq boundary.

```text
Sense transition
    ↓
PeaqEventPublisher
    ↓
official PeaqosClient.submit_event()
    ↓
peaq Activity Event
```

Machine Markets network operations delegate to `client.orchestration`.

## Install

```bash
pip install -e .
pip install -e packages/Sense-peaq
```

Run the offline example:

```bash
PYTHONPATH=src:packages/Sense-peaq/src \
python examples/04_peaq/evaluate.py
```

It uses a fake client so it cannot spend gas.

## Provenance

Default publication is self-reported/off-chain.

For an on-chain-verifiable source:

```python
from sense_peaq import EventProvenance

provenance = EventProvenance.onchain(
    source_chain_id=8453,
    source_tx_hash="0x...",
)
```

Sense rejects hardware-signed trust claims until a real attested-hardware path is
implemented.

## Live verification

For an actual configured peaq transaction, use:

```text
tests/live/test_peaq_activity_event.py
```

See [live test instructions](../../tests/live/README.md).

## Machine Markets

Use `MachineMarketsAdapter` for official orchestration calls and
`check_market_eligibility()` when the application needs to gate a market
candidate using current Sense capability state.

See [sense-peaq](../../packages/Sense-peaq/README.md).
