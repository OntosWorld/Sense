"""ROS 2 mapping contract without requiring a live ROS graph."""

from __future__ import annotations

import sys
import types

from sense_ai import ContextMachine, TelemetryFieldSpec
from sense_ros2 import Ros2SenseBridge


class FakeRosClient:
    def __init__(self) -> None:
        self.callbacks = {}
        self.destroyed = []

    def create_subscription(self, msg_type, topic, callback, qos_profile=10):
        self.callbacks[topic] = callback
        return (msg_type, topic, qos_profile)

    def destroy_subscription(self, subscription):
        self.destroyed.append(subscription)


def test_bridge_maps_message_field_into_sense(monkeypatch) -> None:
    package = types.ModuleType("fake_ros")
    module = types.ModuleType("fake_ros.msg")

    class BatteryState:
        def __init__(self, percentage: float) -> None:
            self.percentage = percentage

    module.BatteryState = BatteryState
    monkeypatch.setitem(sys.modules, "fake_ros", package)
    monkeypatch.setitem(sys.modules, "fake_ros.msg", module)

    machine = ContextMachine()
    machine.define_observation(
        TelemetryFieldSpec("battery.level_pct", kind="number")
    )
    client = FakeRosClient()
    bridge = Ros2SenseBridge.from_dict(
        client,
        machine,
        {
            "topics": [
                {
                    "topic": "/battery_state",
                    "message_type": "fake_ros.msg.BatteryState",
                    "field": "percentage",
                    "target": "battery.level_pct",
                    "transform": "ratio_to_percent",
                    "ttl_ms": 5000,
                }
            ]
        },
    )

    bridge.start()
    client.callbacks["/battery_state"](BatteryState(0.61))

    observation = machine.get_observation("battery.level_pct")
    assert observation is not None
    assert observation.value == 61.0
    assert observation.ttl_ms == 5000

    bridge.stop()
    assert client.destroyed
