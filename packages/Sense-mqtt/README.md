# sense-mqtt

MQTT transport adapter for Sense.

It subscribes to JSON telemetry and runs every payload through the core Sense
normalization and validation pipeline before storing observations.

## Install from source

The Sense packages are not yet published on PyPI. From the repository root:

```bash
pip install -e .
pip install -e packages/Sense-mqtt
```

```python
from sense_mqtt import MqttSenseAdapter

adapter = MqttSenseAdapter.from_dict(
    machine,
    {
        "host": "localhost",
        "topics": [
            {
                "topic": "robot/telemetry",
                "mappings": [
                    {
                        "source": "battery.ratio",
                        "target": "battery.level_pct",
                        "transform": "ratio_to_percent",
                    }
                ],
            }
        ],
    },
)

adapter.start()
# ...
adapter.stop()
```

MQTT is transport only. Capability evaluation remains local in Sense.
