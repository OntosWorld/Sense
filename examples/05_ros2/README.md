# Example 05 — ROS 2 Integration

This example demonstrates bridging ROS 2 topics to Sense observations using `Ros2Client`, with callbacks that translate ROS message types into `TelemetryObservation` objects.

The example includes a mock `rclpy` so it runs without a live ROS 2 graph.

> **Note:** `sense-ros2` is in early development. The `Ros2Client` context manager is functional; declarative topic→path mapping and built-in ROS type adapters are planned.

**Run from the repo root:**

```bash
PYTHONPATH=src:packages/Sense-ros2/src python examples/05_ros2/evaluate.py
```

**Inside a real ROS 2 environment:**

```bash
# In a ROS 2 sourced shell:
PYTHONPATH=src python examples/05_ros2/evaluate.py
```

## What it does

1. Creates a `Ros2Client` as a context manager
2. Declares and reads ROS 2 parameters
3. Subscribes to `/battery/level` (`Float32`) and `/estop/status` (`Bool`)
4. Translates incoming ROS messages into `TelemetryObservation` objects
5. Evaluates the `inspection.ready` capability after each simulated message batch
6. Shows how status changes as telemetry changes

## Key concepts

### Ros2Client context manager

```python
from sense_ros2 import Ros2Client

with Ros2Client(node_name="sense_eval") as client:
    client.declare_parameter("machine_ref", "robot-001")
    ref = client.get_parameter("machine_ref")

    # Create subscriptions and publishers
    sub = client.create_subscription(Float32, "/battery/level", callback)
    pub = client.create_publisher(Bool, "/capability/status", qos_profile=10)
```

### Bridging topics to Sense

```python
from datetime import datetime, timezone
from sense_ai import TelemetryObservation

def on_battery(msg: Float32) -> None:
    machine.observe(TelemetryObservation(
        path="battery.level_pct",
        value=round(msg.data, 1),
        observed_at=datetime.now(timezone.utc),
        source="/battery/level",
    ))
```

### Error handling

```python
from sense_ros2 import Ros2Client

try:
    with Ros2Client(node_name="sense_eval") as client:
        ...
except ImportError as e:
    print("rclpy not available — install ROS 2 Python bindings")
```

### Planned improvements

See [packages/Sense-ros2/README.md](../../packages/Sense-ros2/README.md) for the full roadmap.
