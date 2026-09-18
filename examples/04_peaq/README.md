# Example 04 — peaq Activity Events

Demonstrates the current Sense → peaq integration boundary.

Sense does not mutate DID documents with capability snapshots and does not implement its own Machine Markets listing API.

Instead:

```text
Sense transition
    ↓
PeaqEventPublisher
    ↓
PeaqosClient.submit_event()
    ↓
peaq Activity Event
```

and Machine Markets operations delegate to `client.orchestration`.

## Install

```bash
pip install -e .
pip install -e packages/Sense-peaq
```

Run the example:

```bash
PYTHONPATH=src:packages/Sense-peaq/src \
python examples/04_peaq/evaluate.py
```

The example uses local fake clients so it can run without a funded wallet.

For a real deployment:

```python
from dotenv import load_dotenv
from peaq_os_sdk import PeaqosClient
from sense_peaq import PeaqEventPublisher

load_dotenv()
client = PeaqosClient.from_env()

publisher = PeaqEventPublisher(client, machine_id=42)
```

Use peaq's current setup documentation:

https://docs.peaq.xyz/peaqos/install

For Machine Markets/Scale, configure `PEAQOS_ORCHESTRATION_URL` and use request types from the official `peaq-os-sdk`.

See [sense-peaq](../../packages/Sense-peaq/README.md).
