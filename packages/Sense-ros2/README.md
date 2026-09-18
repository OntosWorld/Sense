# sense-ros2

ROS 2 adapter for Sense.

This package is intentionally thin: ROS 2 remains the transport/runtime and Sense remains the local capability-context engine.

## Status

**Early integration.**

Current functionality:

- ROS 2 node lifecycle;
- parameters;
- subscriptions;
- publishers;
- manual callback mapping from ROS messages to Sense observations.

Not yet provided:

- declarative topic-to-Sense path configuration;
- built-in mappings for common ROS message types;
- launch-file helpers;
- automatic peaq publishing.

## Requirements

Use a supported ROS 2 installation with `rclpy` available in the sourced environment.

Do not rely on `pip install rclpy` as a general installation path. Install ROS 2 using the official ROS documentation for your platform, then source the workspace/environment.

Official docs:

https://docs.ros.org/

## Install Sense adapter

From the repository:

```bash
pip install -e packages/Sense-ros2
```

This package intentionally does not declare `rclpy` as a PyPI dependency because ROS 2 supplies it through the ROS installation.

## Basic use

```python
from sense_ros2 import Ros2Client

with Ros2Client(node_name="sense_eval") as client:
    client.declare_parameter("machine_ref", "robot-001")

    from std_msgs.msg import Float32

    def on_battery(message: Float32) -> None:
        machine.observe(
            "battery.level_pct",
            float(message.data),
            source="/battery/level",
        )

    client.create_subscription(
        Float32,
        "/battery/level",
        on_battery,
        qos_profile=10,
    )
```

## ROS 2 → Sense boundary

The intended architecture is:

```text
ROS 2 topic
    ↓
message callback / adapter
    ↓
Sense observation path
    ↓
ContextMachine
    ↓
capability evaluation
```

Sense does not create a second robot-control protocol.

## Timestamps

Where the ROS message contains a source timestamp, map it to `observed_at`.

Use `received_at` for the local receipt time when needed.

Example:

```python
from datetime import datetime, timezone

from sense_ai import TelemetryObservation

machine.observe(
    TelemetryObservation(
        path="localization.pose",
        value={
            "x": message.pose.position.x,
            "y": message.pose.position.y,
            "z": message.pose.position.z,
        },
        observed_at=source_time,
        received_at=datetime.now(timezone.utc),
        source="/localization/pose",
        ttl_ms=1000,
    )
)
```

## QoS

`Ros2Client.create_subscription()` and `create_publisher()` pass the provided QoS argument to `rclpy`.

Select QoS according to the ROS 2 publisher/subscriber contract. Do not assume a larger queue depth means “higher reliability.”

For sensor-data QoS, reliability, durability and history semantics, follow ROS 2 documentation.

## peaq

peaq already provides its own ROS 2 machine runtime. Sense does not replace it.

A deployment may use both:

```text
ROS 2
 ├─ peaq ROS 2 runtime → peaq operations
 └─ Sense adapter       → physical context/capability evaluation
```

## Example

Run the repository example:

```bash
PYTHONPATH=src:packages/Sense-ros2/src \
python examples/05_ros2/evaluate.py
```

The example includes a local mock for development without a live robot.

## Planned work

- declarative topic → observation mapping;
- common message extractors;
- QoS configuration helpers;
- launch examples;
- clearer integration examples with peaq's ROS 2 runtime.

## License

Apache-2.0.
