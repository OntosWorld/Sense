# sense-ros2

ROS 2 telemetry adapter for Sense 0.3.x.

ROS 2 remains the machine transport/runtime. Sense converts selected message
fields into canonical observations and evaluates current capability locally.

## Install

Install ROS 2 for your platform and source its environment so `rclpy` is
available.

Then:

```bash
pip install -e .
pip install -e packages/Sense-ros2
```

The Sense packages are not yet published on PyPI; these commands must be run
from a source checkout.

The package includes PyYAML for declarative mapping files. It intentionally does
not install `rclpy` from PyPI.

## Declarative bridge

```yaml
topics:
  - topic: /battery_state
    message_type: sensor_msgs.msg.BatteryState
    field: percentage
    target: battery.level_pct
    transform: ratio_to_percent
    ttl_ms: 5000
    qos: 10

  - topic: /localization/pose
    message_type: geometry_msgs.msg.PoseStamped
    field: pose
    target: localization.pose
    ttl_ms: 1000
```

Use it with:

```python
from sense_ros2 import Ros2Client, Ros2SenseBridge

with Ros2Client(node_name="sense") as client:
    bridge = Ros2SenseBridge.from_yaml_file(
        client,
        machine,
        "sense_ros2.yaml",
    )
    bridge.start()
    client.spin()
```

Each message follows:

```text
ROS 2 message
    ↓
configured field extraction
    ↓
Sense transform / validation
    ↓
canonical observation
    ↓
capability evaluation by application
```

## Source timestamps

The bridge reads `header.stamp` by default when present and uses it as
`observed_at`. Local arrival time becomes `received_at`.

Override or disable with `timestamp_path`.

## QoS

`qos` is passed to `rclpy.create_subscription()`.

Choose QoS according to the publisher/subscriber contract; Sense does not alter
ROS reliability, durability, or history semantics.

## Lifecycle

`Ros2Client` supports:

- context-managed node lifecycle;
- subscriptions and publishers;
- parameters;
- subscription destruction;
- `spin()`;
- `spin_once()`.

`Ros2SenseBridge.stop()` removes subscriptions without shutting down a client
owned elsewhere.

## peaq boundary

Sense does not replace peaq's ROS runtime.

A deployment may use:

```text
ROS 2
 ├─ robot control / OEM graph
 ├─ peaq ROS runtime
 └─ sense-ros2 → normalized physical context
```

External peaq publication should remain explicit application behavior.

## Tests

The fast adapter contract test uses a fake ROS message/client and does not
require a live ROS graph:

```bash
pytest packages/Sense-ros2/tests/test_mapping.py -v
```

Developers with Docker can run the real DDS integration test without installing
ROS 2 on the host:

```bash
bash scripts/test-ros2-runtime.sh
```

The helper starts the official `ros:jazzy-ros-base` image, publishes a real
`std_msgs/Float32` message, spins the subscriber, and verifies the normalized
observation stored by Sense.

A real robot/ROS deployment should additionally verify message types, QoS, frame
semantics, and clock synchronization.

## License

Apache-2.0.
