# sense-http

HTTP polling transport adapter for Sense.

## Install from source

The Sense packages are not yet published on PyPI. From the repository root:

```bash
pip install -e .
pip install -e packages/Sense-http
```

```python
from sense_http import HttpPollingAdapter

adapter = HttpPollingAdapter(
    machine,
    normalizer,
    url="http://robot.local/telemetry",
    interval_sec=1.0,
)

adapter.start()
# ...
adapter.stop()
```

Use `poll_once()` when an application already owns its scheduling loop.
