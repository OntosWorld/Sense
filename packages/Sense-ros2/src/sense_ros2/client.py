"""Thin ROS 2 client wrapper used by the Sense adapter."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class Ros2Client:
    """Manage a small rclpy node for Sense telemetry bridges."""

    def __init__(
        self,
        node_name: str = "sense_ai_client",
        namespace: str | None = None,
    ) -> None:
        self.node_name = node_name
        self.namespace = namespace
        self._node: Any = None
        self._owns_context = False

    def __enter__(self) -> "Ros2Client":
        try:
            import rclpy
            from rclpy.node import Node
        except ImportError as exc:
            raise ImportError(
                "ROS 2 Python bindings are required. Install ROS 2 for your "
                "platform and source its environment before using sense-ros2."
            ) from exc

        is_running = bool(getattr(rclpy, "ok", lambda: False)())
        if not is_running:
            rclpy.init()
            self._owns_context = True

        self._node = Node(self.node_name, namespace=self.namespace)
        logger.info("ROS 2 client started: %s", self.node_name)
        return self

    def __exit__(self, *args: object) -> None:
        if self._node is not None:
            self._node.destroy_node()
            self._node = None

        if self._owns_context:
            import rclpy

            if bool(getattr(rclpy, "ok", lambda: True)()):
                rclpy.shutdown()
            self._owns_context = False

        logger.info("ROS 2 client stopped")

    @property
    def node(self) -> Any:
        """Return the underlying rclpy node while the context is active."""
        if self._node is None:
            raise RuntimeError("Ros2Client must be used inside a with block")
        return self._node

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Read a declared ROS 2 parameter."""
        if not self.node.has_parameter(name):
            return default
        return self.node.get_parameter(name).value

    def declare_parameter(self, name: str, default_value: Any = None) -> None:
        """Declare a ROS 2 parameter."""
        self.node.declare_parameter(name, default_value)

    def create_subscription(
        self,
        msg_type: type,
        topic: str,
        callback: Callable[[Any], None],
        qos_profile: Any = 10,
    ) -> Any:
        """Subscribe to a ROS 2 topic."""
        return self.node.create_subscription(
            msg_type,
            topic,
            callback,
            qos_profile,
        )

    def create_publisher(
        self,
        msg_type: type,
        topic: str,
        qos_profile: Any = 10,
    ) -> Any:
        """Create a ROS 2 publisher."""
        return self.node.create_publisher(msg_type, topic, qos_profile)
