"""Declarative ROS 2 topic-to-Sense telemetry bridge."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sense_ai import ContextMachine
from sense_ai.telemetry import (
    TelemetryMapping,
    TelemetryNormalizer,
    TransformSpec,
)

from .client import Ros2Client


@dataclass(frozen=True, slots=True)
class RosTopicMapping:
    """Map one ROS 2 message field into one canonical Sense observation."""

    topic: str
    message_type: str
    field: str
    target: str
    transforms: tuple[TransformSpec, ...] = ()
    ttl_ms: int | None = None
    qos: int = 10
    timestamp_path: str | None = "header.stamp"
    source: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RosTopicMapping:
        transform_values: list[str | dict[str, Any]] = []
        if "transform" in data:
            transform_values.append(data["transform"])
        raw_many = data.get("transforms", [])
        if isinstance(raw_many, list):
            transform_values.extend(raw_many)
        return cls(
            topic=str(data["topic"]),
            message_type=str(data["message_type"]),
            field=str(data.get("field", "")),
            target=str(data["target"]),
            transforms=tuple(
                TransformSpec.from_value(item) for item in transform_values
            ),
            ttl_ms=_optional_int(data.get("ttl_ms")),
            qos=int(data.get("qos", 10)),
            timestamp_path=(
                str(data["timestamp_path"])
                if data.get("timestamp_path") is not None
                else None
            ),
            source=str(data["source"]) if data.get("source") else None,
        )


class Ros2SenseBridge:
    """Subscribe to ROS topics and feed normalized telemetry into Sense."""

    def __init__(
        self,
        client: Ros2Client,
        machine: ContextMachine,
        mappings: list[RosTopicMapping],
    ) -> None:
        self._client = client
        self._machine = machine
        self._mappings = list(mappings)
        self._subscriptions: list[Any] = []
        self._normalizers: dict[str, TelemetryNormalizer] = {
            mapping.topic: TelemetryNormalizer(
                [
                    TelemetryMapping(
                        source_path=mapping.field,
                        target_path=mapping.target,
                        transforms=mapping.transforms,
                        ttl_ms=mapping.ttl_ms,
                        source=mapping.source or mapping.topic,
                        required=True,
                    )
                ],
                schema=machine.telemetry_schema,
            )
            for mapping in mappings
        }

    @classmethod
    def from_dict(
        cls,
        client: Ros2Client,
        machine: ContextMachine,
        data: dict[str, Any],
    ) -> Ros2SenseBridge:
        raw = data.get("topics", [])
        if not isinstance(raw, list):
            raise ValueError("ROS mapping config topics must be a list")
        mappings = [RosTopicMapping.from_dict(item) for item in raw if isinstance(item, dict)]
        return cls(client, machine, mappings)

    @classmethod
    def from_yaml_file(
        cls,
        client: Ros2Client,
        machine: ContextMachine,
        path: str | Path,
    ) -> "Ros2SenseBridge":
        try:
            import yaml
        except ImportError as exc:
            raise ImportError(
                "PyYAML is required for ROS mapping files; install sense-ros2"
            ) from exc
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("ROS mapping YAML must contain an object")
        return cls.from_dict(client, machine, raw)

    def start(self) -> None:
        """Create all configured ROS subscriptions."""
        if self._subscriptions:
            return
        for mapping in self._mappings:
            msg_type = _import_type(mapping.message_type)

            def callback(message: Any, *, current: RosTopicMapping = mapping) -> None:
                observed_at = _extract_timestamp(message, current.timestamp_path)
                result = self._normalizers[current.topic].normalize(
                    message,
                    observed_at=observed_at,
                    received_at=datetime.now(timezone.utc),
                    source=current.source or current.topic,
                )
                for observation in result.observations:
                    self._machine.observe(observation)

            subscription = self._client.create_subscription(
                msg_type,
                mapping.topic,
                callback,
                mapping.qos,
            )
            self._subscriptions.append(subscription)

    def stop(self) -> None:
        """Destroy bridge subscriptions while leaving the ROS client alive."""
        for subscription in self._subscriptions:
            self._client.destroy_subscription(subscription)
        self._subscriptions.clear()

    @property
    def mappings(self) -> tuple[RosTopicMapping, ...]:
        return tuple(self._mappings)


def _import_type(path: str) -> type:
    module_name, _, attr = path.rpartition(".")
    if not module_name or not attr:
        raise ValueError(
            "message_type must be a fully qualified class, "
            "e.g. sensor_msgs.msg.BatteryState"
        )
    module = importlib.import_module(module_name)
    value = getattr(module, attr)
    if not isinstance(value, type):
        raise TypeError(f"{path} does not resolve to a class")
    return value


def _extract_timestamp(message: Any, path: str | None) -> datetime | None:
    if path is None:
        return None
    current = message
    for segment in path.split("."):
        if not hasattr(current, segment):
            return None
        current = getattr(current, segment)

    sec = getattr(current, "sec", None)
    nanosec = getattr(current, "nanosec", None)
    if isinstance(sec, int) and isinstance(nanosec, int):
        return datetime.fromtimestamp(
            sec + (nanosec / 1_000_000_000),
            tz=timezone.utc,
        )
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected integer")
    return value
