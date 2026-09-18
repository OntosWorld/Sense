# sense-ros2

Early ROS 2 adapter for Sense.

The package intentionally stays outside the Sense core so the capability engine can run without ROS 2.

## Status

Current implementation provides a thin `rclpy` wrapper for:

- node lifecycle;
- parameters;
- topic subscriptions;
- publishers.

Declarative ROS-topic-to-Sense observation mapping is still planned.

## Install

First install Sense:

```bash
pip install -e .
```

Then install the adapter:

```bash
pip install -e packages/Sense-ros2
```

A working ROS 2 environment with `rclpy` must already be available. Install ROS 2 and `rclpy` using the instructions for your ROS distribution rather than assuming a generic PyPI installation will provide a complete ROS runtime.

## Basic usage

```python
from sense_ai import ContextMachine, capability, equals, gte
from sense_ros2 import Ros2Client

machine = ContextMachine(machine_ref="robot-001")
machine.define_capability(
    capability(
        "navigation.active",
        requires=[
            equals("safety.estop", False),
            gte("battery.level_pct", 20),
        ],
    )
)

with Ros2Client(node_name="sense_eval") as client:
    from std_msgs.msg import Bool, Float32

    def on_battery(msg: Float32) -> None:
        machine.observe("battery.level_pct", msg.data, source="/battery/level")

    def on_estop(msg: Bool) -> None:
        machine.observe("safety.estop", msg.data, source="/estop/status")

    client.create_subscription(Float32, "/battery/level", on_battery)
    client.create_subscription(Bool, "/estop/status", on_estop)
```

## Architecture boundary

The ROS adapter should translate ROS state into Sense observations:

```text
ROS 2 topic
    ↓
message field extraction
    ↓
Sense observation path
    ↓
timestamp / source / TTL
    ↓
ContextMachine.observe()
```

The adapter is not a robot controller, planner, action server abstraction, or replacement for ROS 2.

## Planned work

- declarative topic-to-path configuration;
- common message extractors;
- QoS-aware adapter configuration;
- use source message timestamps where available;
- integration tests in a real ROS 2 workspace;
- transition hooks that can be wired to optional peaq publishing by application code.

Automatic peaq publication should remain opt-in and should not be hard-wired into ROS callbacks.

## License

Apache-2.0.
