# sense-http

HTTP polling transport adapter for Sense.

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
