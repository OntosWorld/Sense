"""ROS 2 client for Sense AI — thin wrapper around rclpy."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class Ros2Client:
    """
    Thin wrapper around rclpy for interacting with the ROS 2 graph.

    Handles node lifecycle, topic subscription/publishing, and service calls
    on behalf of the Sense AI evaluation framework.

    Parameters
    ----------
    node_name : str
        Name for the ROS 2 node (must be unique in the graph).
    namespace : str, optional
        ROS 2 namespace for this node.
    """

    def __init__(
        self,
        node_name: str = "sense_ai_client",
        namespace: str | None = None,
    ) -> None:
        self.node_name = node_name
        self.namespace = namespace
        self._node: Any = None  # rclpy.node.Node — initialised on enter_context()

    def __enter__(self) -> Ros2Client:
        try:
            import rclpy
        except ImportError as exc:
            raise ImportError(
                "ROS 2 Python client (rclpy) is required. "
                "Install it: pip install rclpy"
            ) from exc

        rclpy.init()
        self._node = rclpy.node.Node(self.node_name, namespace=self.namespace)
        logger.info("ROS 2 client started: %s", self.node_name)
        return self

    def __exit__(self, *args: object) -> None:
        if self._node:
            self._node.destroy_node()
        import rclpy  # noqa: PLC0415
        rclpy.shutdown()
        logger.info("ROS 2 client stopped")

    @property
    def node(self) -> Any:
        """The underlying rclpy node."""
        if self._node is None:
            raise RuntimeError(
                "Ros2Client is not active. "
                "Use it inside a `with` block or call __enter__ first."
            )
        return self._node

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """Get a ROS 2 parameter from the node."""
        return self.node.get_parameter(name).value if self.node.has_parameter(name) else default

    def declare_parameter(self, name: str, default_value: Any = None) -> None:
        """Declare a ROS 2 parameter on the node."""
        self.node.declare_parameter(name, default_value)

    def create_subscription(
        self,
        msg_type: type,
        topic: str,
        callback: Any,
        qos_profile: int = 10,
    ) -> Any:
        """Subscribe to a ROS 2 topic."""
        return self.node.create_subscription(msg_type, topic, callback, qos_profile)

    def create_publisher(
        self,
        msg_type: type,
        topic: str,
        qos_profile: int = 10,
    ) -> Any:
        """Create a ROS 2 publisher on a topic."""
        return self.node.create_publisher(msg_type, topic, qos_profile)
