"""
ROS 2 integration: bridge ROS 2 topics to Sense observations using
Ros2Client, with callbacks that translate message types into
TelemetryObservation objects.

This example runs without a live ROS 2 graph by mocking rclpy.
In a real deployment, remove the mock and run inside a ROS 2 environment.

Run from the repo root::

    PYTHONPATH=src:packages/Sense-ros2/src python examples/05_ros2/evaluate.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from types import ModuleType
from typing import Any

from sense_ai import (
    ContextMachine,
    TelemetryObservation,
    capability,
    equals,
    gte,
)


# ── Mock rclpy so this example runs outside a ROS 2 environment ───────────────

class _MockMsg:
    pass


class _MockFloat32:
    data: float

    def __init__(self, data: float) -> None:
        self.data = data


class _MockBool:
    data: bool

    def __init__(self, data: bool) -> None:
        self.data = data


class _MockPoseStamped:
    class _Pose:
        class _Position:
            x: float
            y: float
            z: float

        position: _Position

    pose: _Pose


class _MockRclpy:
    version = "2.0.0-mock"
    qos = type("qos", (), {"QoSProfile": object})()

    class node:
        @staticmethod
        class Node:
            def __init__(self, name: str, *, namespace: str | None = None) -> None:
                self.name = name
                self.namespace = namespace
                self._params: dict[str, Any] = {}
                self._subscriptions: dict[str, tuple[Any, Any]] = {}
                self._publishers: dict[str, Any] = {}

            def has_parameter(self, name: str) -> bool:
                return name in self._params

            def get_parameter(self, name: str) -> Any:
                return type("p", (), {"value": self._params.get(name)})()

            def declare_parameter(self, name: str, default_value: Any = None) -> None:
                self._params[name] = default_value

            def create_subscription(
                self,
                msg_type: type,
                topic: str,
                callback: Any,
                qos_profile: int = 10,
            ) -> Any:
                self._subscriptions[topic] = (msg_type, callback)
                return topic

            def create_publisher(
                self,
                msg_type: type,
                topic: str,
                qos_profile: int = 10,
            ) -> Any:
                pub = type("pub", (), {"topic": topic, "msg_type": msg_type})()
                self._publishers[topic] = pub
                return pub

            def destroy_node(self) -> None:
                pass

            def get_logger(self) -> Any:
                return type(
                    "logger",
                    (),
                    {"info": lambda self, m: None, "warn": lambda self, m: None},
                )()

            # Test helper: simulate receiving a message on a topic
            def _inject(self, topic: str, msg: Any) -> None:
                if topic in self._subscriptions:
                    _, cb = self._subscriptions[topic]
                    cb(msg)


def _install_mock_rclpy() -> None:
    """Replace rclpy with our mock for environments without ROS 2.

    Installs a plain mock object at sys.modules["rclpy"] so that the
    ``import rclpy`` inside sense_ros2.client.Ros2Client.__enter__ finds it
    and receives our mock instead of the real library.
    """
    mock = type("rclpy", (), {
        "__name__": "rclpy",
        "__version__": "2.0.0-mock",
        "init": lambda *args, **kwargs: None,
        "shutdown": lambda *args, **kwargs: None,
        "node": _MockRclpy.node,
        "qos": _MockRclpy.qos,
    })()
    sys.modules["rclpy"] = mock  # type: ignore


# ── Example: ROS 2 → Sense bridge ────────────────────────────────────────────

def _main() -> None:
    # Install mock rclpy so this example runs without ROS 2
    _install_mock_rclpy()

    from sense_ros2 import Ros2Client

    # ── 1. Set up the Sense machine ───────────────────────────────────────────

    machine = ContextMachine(machine_ref="inspection-robot-01")
    machine.define_capability(
        capability(
            "inspection.ready",
            version="1.0",
            requires=[
                equals("safety.estop", False),
                gte("battery.level_pct", 20),
            ],
        )
    )

    # ── 2. Bridge ROS 2 topics → Sense observations ────────────────────────────

    with Ros2Client(node_name="sense_eval") as client:
        print(f"ROS 2 node started: {client.node.name}")

        # Declare parameters
        client.declare_parameter("machine_ref", "inspection-robot-01")
        client.declare_parameter("evaluation_interval_s", 5.0)

        # Subscribe to battery level
        def on_battery(msg: _MockFloat32) -> None:
            machine.observe(
                TelemetryObservation(
                    path="battery.level_pct",
                    value=round(msg.data, 1),
                    observed_at=datetime.now(timezone.utc),
                    source="/battery/level",
                )
            )

        # Subscribe to estop status
        def on_estop(msg: _MockBool) -> None:
            # ROS publishes estop=True when engaged; Sense wants False when released
            machine.observe(
                TelemetryObservation(
                    path="safety.estop",
                    value=msg.data,
                    observed_at=datetime.now(timezone.utc),
                    source="/estop/status",
                )
            )

        client.create_subscription(_MockFloat32, "/battery/level", on_battery)
        client.create_subscription(_MockBool, "/estop/status", on_estop)

        # ── 3. Simulate messages flowing in ──────────────────────────────────

        print("\n  Simulating ROS 2 topic messages…")

        # Healthy state
        client.node._inject("/battery/level", _MockFloat32(74.0))
        client.node._inject("/estop/status", _MockBool(False))

        result = machine.evaluate("inspection.ready")
        print(f"  Battery 74%, estop released → {result.status.name}")

        # Low battery warning
        client.node._inject("/battery/level", _MockFloat32(18.0))
        result = machine.evaluate("inspection.ready")
        print(f"  Battery 18%, estop released → {result.status.name}")

        # Estop engaged
        client.node._inject("/estop/status", _MockBool(True))
        result = machine.evaluate("inspection.ready")
        print(f"  Battery 18%, estop engaged → {result.status.name}")

        # Restore healthy
        client.node._inject("/battery/level", _MockFloat32(74.0))
        client.node._inject("/estop/status", _MockBool(False))
        result = machine.evaluate("inspection.ready")
        print(f"  Battery 74%, estop released → {result.status.name}")

        print(f"\n  Snapshot observations: {len(machine.snapshot().observations)} fields")


def main() -> None:
    try:
        _main()
    except ImportError as e:
        if "rclpy" in str(e):
            print("ROS 2 (rclpy) not available — run inside a ROS 2 environment")
            print("or use the mock rclpy mode by setting ROS2_MOCK=1:")
            print()
            print("  ROS2_MOCK=1 PYTHONPATH=src:packages/Sense-ros2/src python examples/05_ros2/evaluate.py")
            sys.exit(1)
        raise


if __name__ == "__main__":
    main()
