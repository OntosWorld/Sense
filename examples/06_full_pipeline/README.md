# Example 06 — complete raw telemetry pipeline

This is the reference path for Sense:

```text
raw OEM-style payload
    ↓
schema validation
    ↓
normalization / transforms
    ↓
canonical Sense observations
    ↓
freshness + capability rules
    ↓
AVAILABLE / DEGRADED / UNAVAILABLE / UNKNOWN
    ↓
structured transitions
    ↓
privacy-safe snapshot
```

Run from the repository root:

```bash
PYTHONPATH=src python examples/06_full_pipeline/evaluate.py
```

The three replay frames move `warehouse.pick` through:

```text
AVAILABLE
→ DEGRADED
→ UNAVAILABLE
```

The same `sense.json` telemetry mappings can be reused by ROS 2, MQTT, HTTP,
or an OEM-specific adapter.
