# sense-peaq

Official peaqOS adapter for Sense.

The package connects Sense's local physical-context engine to the documented peaqOS Python SDK.

```text
machine telemetry
    ↓
Sense capability state
    ↓
structured transition / snapshot
    ↓
peaq-os-sdk
    ↓
Activity Events / Machine Markets orchestration
```

## Install

From the repository root:

```bash
pip install -e .
pip install -e packages/Sense-peaq
```

The adapter depends on:

```text
sense-ai >= 0.2.0
peaq-os-sdk >= 0.8.0
```

## Activity Events

`PeaqContextPublisher` submits selected Sense output through the official `PeaqosClient.submit_event()` API.

```python
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqContextPublisher

client = PeaqosClient.from_env()
publisher = PeaqContextPublisher(client, machine_id=123)

transition = machine.last_transition("warehouse.pick")
if transition:
    result = publisher.publish_transition(
        transition,
        machine_ref=machine.machine_ref,
    )
    print(result.tx_hash)
    print(result.data_hash_hex)
```

Sense submits an Activity Event with:

- event type: peaq `EVENT_TYPE_ACTIVITY`;
- value: `0`;
- currency: empty string;
- trust level: `TRUST_SELF_REPORTED` by default;
- raw data: compact JSON containing the selected Sense transition or snapshot;
- metadata: Sense producer/schema metadata.

Sense does not claim an event is on-chain-verifiable or hardware-signed automatically.

## Snapshot publishing

```python
publisher.publish_snapshot(machine.snapshot())
```

Raw observations are excluded by default.

To include evidence, provide an explicit allowlist:

```python
publisher.publish_snapshot(
    machine.snapshot(),
    include_observations=True,
    observation_allowlist=("battery.*", "localization.status"),
)
```

This is intentionally explicit to prevent accidental machine-telemetry disclosure.

## Machine Markets

`MachineMarketsAdapter` delegates to the official `client.orchestration` namespace.

```python
from sense_peaq import MachineMarketsAdapter

markets = MachineMarketsAdapter(client)

machines = markets.list_machines(limit=20)
services = markets.list_market_services(limit=20)
```

For an agent-authorized market search:

```python
search = markets.search_market(params, pairing_token)
```

The adapter does **not** implement a custom Sense listing registry, bidding API, or undocumented peaq endpoints.

## Runtime context

`to_market_context()` creates local Sense runtime context:

```python
from sense_peaq import to_market_context

context = to_market_context(machine.snapshot())
print(context.to_dict())
```

This context is not a peaq listing schema. It is application-level physical-state information that can be used alongside peaq machine/service/market data.

## Configuration

The official peaq client can be configured with:

```python
from peaq_os_sdk import PeaqosClient

client = PeaqosClient.from_env()
```

Follow current peaqOS documentation for required RPC, contract, Tokenomics, orchestration, and wallet settings.

For Machine Markets/Scale, configure `PEAQOS_ORCHESTRATION_URL`.

## Security

Sense core does not manage peaq credentials.

The adapter receives an already-configured `PeaqosClient`. Depending on how that client is created, key custody may be handled by environment configuration or peaq's supported wallet mechanisms.

Do not log or serialize private keys, wallet secrets, pairing tokens, or API keys.

## Errors

Sense wraps adapter failures in its typed peaq errors:

```python
from sense_ai import PeaqConfigurationError, PeaqNetworkError
```

SDK configuration errors are surfaced as `PeaqConfigurationError`. Network/orchestration/event-submission errors are surfaced as `PeaqNetworkError`.

## Source of truth

Do not add peaq functionality from memory or old examples. Verify against current official peaqOS documentation before changing this adapter.

## License

Apache-2.0.
