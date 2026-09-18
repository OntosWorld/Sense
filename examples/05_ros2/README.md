# Example 05 — ROS 2 Bridge

Demonstrates manually mapping ROS 2 messages into Sense observations.

Run the repository mock example:

```bash
pip install -e .
pip install -e packages/Sense-ros2

PYTHONPATH=src:packages/Sense-ros2/src \
python examples/05_ros2/evaluate.py
```

Architecture:

```text
ROS 2 topic
    ↓
callback
    ↓
TelemetryObservation / machine.observe()
    ↓
Sense capability evaluation
```

The ROS 2 adapter is early-stage. Declarative topic mapping and built-in message extractors are planned.

In a real robot environment, install ROS 2 using the official ROS instructions and source the environment so `rclpy` is available.

https://docs.ros.org/

Sense does not replace ROS 2 and does not replace peaq's ROS 2 machine runtime.

See [sense-ros2](../../packages/Sense-ros2/README.md).
