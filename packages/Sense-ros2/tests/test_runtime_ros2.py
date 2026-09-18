"""Real ROS 2 runtime integration test.

This test requires a sourced ROS 2 environment with rclpy and std_msgs.
It publishes a message through DDS and verifies the Sense bridge receives,
normalizes, and stores it.
"""

from __future__ import annotations

import time

import pytest

from sense_ai import ContextMachine, TelemetryFieldSpec
from sense_ros2 import Ros2Client, Ros2SenseBridge


def test_ros2_dds_message_reaches_sense() -> None:
    from std_msgs.msg import Float32

    machine = ContextMachine(machine_ref="ros-runtime-test")
    machine.define_observation(
        TelemetryFieldSpec(
            "battery.level_pct",
            kind="number",
            minimum=0,
            maximum=100,
        )
    )

    with Ros2Client(node_name="sense_runtime_test") as client:
        bridge = Ros2SenseBridge.from_dict(
            client,
            machine,
            {
                "topics": [
                    {
                        "topic": "/sense_runtime/battery",
                        "message_type": "std_msgs.msg.Float32",
                        "field": "data",
                        "target": "battery.level_pct",
                        "transform": "ratio_to_percent",
                        "ttl_ms": 5000,
                        "qos": 10,
                        "timestamp_path": None,
                    }
                ]
            },
        )
        bridge.start()
        publisher = client.create_publisher(
            Float32,
            "/sense_runtime/battery",
            10,
        )

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            message = Float32()
            message.data = 0.73
            publisher.publish(message)
            client.spin_once(timeout_sec=0.2)

            observation = machine.get_observation("battery.level_pct")
            if observation is not None:
                break
            time.sleep(0.1)

        bridge.stop()

    observation = machine.get_observation("battery.level_pct")
    assert observation is not None
    assert observation.value == pytest.approx(73.0, rel=1e-6)
    assert observation.source == "/sense_runtime/battery"
    assert observation.ttl_ms == 5000
