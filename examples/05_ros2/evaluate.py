"""ROS 2 to Sense bridge example with a small local rclpy mock."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from sense_ai import ContextMachine, capability, equals, gte


class MockNode:
    def __init__(self, name: str, *, namespace: str | None = None) -> None:
        self.name = name
        self.namespace = namespace
        self._params: dict[str, Any] = {}
        self._subscriptions: dict[str, tuple[type, Any]] = {}

    def has_parameter(self, name: str) -> bool:
        return name in self._params

    def get_parameter(self, name: str) -> Any:
        return type("Parameter", (), {"value": self._params[name]})()

    def declare_parameter(self, name: str, default_value: Any = None) -> None:
        self._params[name] = default_value

    def create_subscription(
        self,
        msg_type: type,
        topic: str,
        callback: Any,
        qos_profile: Any = 10,
    ) -> str:
        self._subscriptions[topic] = (msg_type, callback)
        return topic

    def create_publisher(
        self,
        msg_type: type,
        topic: str,
        qos_profile: Any = 10,
    ) -> Any:
        return type("Publisher", (), {"topic": topic, "msg_type": msg_type})()

    def destroy_node(self) -> None:
        pass

    def inject(self, topic: str, message: Any) -> None:
        _, callback = self._subscriptions[topic]
        callback(message)


class Float32:
    def __init__(self, data: float) -> None:
        self.data = data


class Bool:
    def __init__(self, data: bool) -> None:
        self.data = data


def install_mock_rclpy() -> None:
    state = {"ok": False}

    package = ModuleType("rclpy")

    def init() -> None:
        state["ok"] = True

    def shutdown() -> None:
        state["ok"] = False

    package.init = init  # type: ignore[attr-defined]
    package.shutdown = shutdown  # type: ignore[attr-defined]
    package.ok = lambda: state["ok"]  # type: ignore[attr-defined]

    node_module = ModuleType("rclpy.node")
    node_module.Node = MockNode  # type: ignore[attr-defined]

    sys.modules["rclpy"] = package
    sys.modules["rclpy.node"] = node_module


def main() -> None:
    install_mock_rclpy()

    from sense_ros2 import Ros2Client

    machine = ContextMachine(machine_ref="inspection-robot-01")
    machine.define_capability(
        capability(
            "inspection.ready",
            requires=[
                equals("safety.estop", False),
                gte("battery.level_pct", 20),
            ],
        )
    )

    with Ros2Client(node_name="sense_eval") as client:
        def on_battery(message: Float32) -> None:
            machine.observe(
                "battery.level_pct",
                float(message.data),
                source="/battery/level",
            )

        def on_estop(message: Bool) -> None:
            machine.observe(
                "safety.estop",
                bool(message.data),
                source="/estop/status",
            )

        client.create_subscription(Float32, "/battery/level", on_battery)
        client.create_subscription(Bool, "/estop/status", on_estop)

        client.node.inject("/battery/level", Float32(74.0))
        client.node.inject("/estop/status", Bool(False))
        print("healthy:", machine.evaluate("inspection.ready").status.value)

        client.node.inject("/battery/level", Float32(18.0))
        print("low battery:", machine.evaluate("inspection.ready").status.value)

        client.node.inject("/estop/status", Bool(True))
        print("estop:", machine.evaluate("inspection.ready").status.value)


if __name__ == "__main__":
    main()
