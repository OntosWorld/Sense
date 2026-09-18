# sense-ros2

ROS 2 adapter for the Sense AI evaluation framework.

Provides a thin `Ros2Client` context manager that wraps `rclpy` to bridge the ROS 2 graph with Sense capability evaluation.

> **Status note:** This package is in early development. `Ros2Client` handles node lifecycle, topic subscriptions, and publishers. Topic-to-Sense path mapping, QoS configuration helpers, and worked examples are in progress.

## Installation

```bash
pip install sense-ros2
```

Requires a ROS 2 environment with `rclpy` installed. Verify with:

```bash
python -c "import rclpy; print(rclpy.__version__)"
```

## Quick start

```python
from sense_ros2 import Ros2Client

with Ros2Client(node_name="sense_eval") as client:
    # Declare parameters
    client.declare_parameter("machine_ref", "robot-001")
    client.declare_parameter("peaq_did", "did:peaq:0x...")

    # Read parameters
    machine_ref = client.get_parameter("machine_ref")

    # Create a subscription
    from std_msgs.msg import Float32
    def on_battery(data: Float32) -> None:
        print(f"Battery: {data.data}%")

    client.create_subscription(Float32, "/battery/level", on_battery)

    # Keep the node alive
    client.node.get_logger().info("Sense ROS 2 node running")
```

## Ros2Client

A context-manager wrapper around `rclpy.node.Node`.

```python
class Ros2Client:
    def __init__(
        self,
        node_name: str = "sense_ai_client",
        namespace: str | None = None,
    ) -> None: ...

    def __enter__(self) -> Ros2Client: ...
    def __exit__(self, *args: object) -> None: ...

    @property
    def node(self) -> rclpy.node.Node:
        """The underlying rclpy node (available only inside the context)."""
        ...

    def get_parameter(self, name: str, default: Any = None) -> Any: ...
    def declare_parameter(self, name: str, default_value: Any = None) -> None: ...

    def create_subscription(
        self,
        msg_type: type,
        topic: str,
        callback: Callable,
        qos_profile: int = 10,
    ) -> rclpy.node.Publisher: ...

    def create_publisher(
        self,
        msg_type: type,
        topic: str,
        qos_profile: int = 10,
    ) -> rclpy.node.Publisher: ...
```

## Using with Sense AI

Combine `Ros2Client` with the core `sense-ai` SDK to build a full evaluation pipeline:

```python
from datetime import datetime, timezone
from sense_ai import ContextMachine, TelemetryObservation, capability, gte, equals
from sense_ros2 import Ros2Client
from std_msgs.msg import Float32, Bool
from geometry_msgs.msg import PoseStamped

# Set up Sense machine
machine = ContextMachine(machine_ref="robot-001")
machine.define_capability(
    capability(
        "navigation.active",
        requires=[
            equals("estop.released", True),
            gte("battery.level_pct", 20),
        ],
    )
)

# Bridge ROS 2 topics → Sense observations
with Ros2Client(node_name="sense_eval") as client:
    def on_battery(msg: Float32) -> None:
        machine.observe("battery.level_pct", msg.data)

    def on_estop(msg: Bool) -> None:
        machine.observe("estop.released", not msg.data)

    def on_pose(msg: PoseStamped) -> None:
        machine.observe(TelemetryObservation(
            path="localization.pose",
            value={"x": msg.pose.position.x, "y": msg.pose.position.y},
            observed_at=datetime.now(timezone.utc),
            source="localization",
        ))

    client.create_subscription(Float32, "/battery/level", on_battery)
    client.create_subscription(Bool, "/estop/status", on_estop)
    client.create_subscription(PoseStamped, "/localization/pose", on_pose)

    # Evaluate on demand
    result = machine.evaluate("navigation.active")
    print(result.status)
```

## QoS Profiles

The default QoS profile is `rclpy.qos.QoSProfile(depth=10)`. Pass a profile integer to adjust:

```python
# High-reliability sensor data
client.create_subscription(Float32, "/safety/estop", on_estop, qos_profile=25)

# Best-effort telemetry (high volume)
client.create_subscription(FloatImage, "/camera/feed", on_image, qos_profile=1)
```

## Error handling

`Ros2Client` raises `ImportError` if `rclpy` is not available:

```python
from sense_ros2 import Ros2Client

try:
    with Ros2Client(node_name="sense_eval") as client:
        ...
except ImportError as e:
    print("ROS 2 not installed — install with: pip install rclpy")
```

## Planned improvements

- [ ] `TelemetryAdapter` interface for declarative topic→path mapping
- [ ] Built-in message adapters for common ROS types (`Float32`, `Bool`, `PoseStamped`, `JointState`, `SensorBatteryState`)
- [ ] Automatic DID publishing via `PeaqContextPublisher` on transition events
- [ ] Launch-file integration example

## License

Apache-2.0
