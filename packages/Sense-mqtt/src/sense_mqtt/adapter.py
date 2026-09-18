"""MQTT transport adapter for normalized Sense telemetry."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sense_ai import ContextMachine
from sense_ai.adapters import TelemetryAdapter
from sense_ai.telemetry import TelemetryMapping, TelemetryNormalizer


@dataclass(frozen=True, slots=True)
class MqttTopicConfig:
    """One MQTT topic and the mappings applied to its JSON payload."""

    topic: str
    normalizer: TelemetryNormalizer
    qos: int = 0


class MqttSenseAdapter(TelemetryAdapter):
    """Subscribe to JSON MQTT telemetry and feed canonical observations to Sense."""

    def __init__(
        self,
        machine: ContextMachine,
        *,
        host: str,
        topics: list[MqttTopicConfig],
        port: int = 1883,
        keepalive: int = 60,
        username: str | None = None,
        password: str | None = None,
        client: Any = None,
    ) -> None:
        self._machine = machine
        self._host = host
        self._port = port
        self._keepalive = keepalive
        self._topics = list(topics)
        self._username = username
        self._password = password
        self._client = client
        self._running = False
        self.errors: list[str] = []

    @classmethod
    def from_dict(
        cls,
        machine: ContextMachine,
        data: dict[str, Any],
        *,
        client: Any = None,
    ) -> MqttSenseAdapter:
        raw_topics = data.get("topics", [])
        if not isinstance(raw_topics, list):
            raise ValueError("mqtt topics must be a list")

        topics: list[MqttTopicConfig] = []
        for raw in raw_topics:
            if not isinstance(raw, dict):
                raise ValueError("mqtt topic entries must be objects")
            raw_mappings = raw.get("mappings", [])
            if not isinstance(raw_mappings, list):
                raise ValueError("mqtt topic mappings must be a list")
            normalizer = TelemetryNormalizer(
                [
                    TelemetryMapping.from_dict(item)
                    for item in raw_mappings
                    if isinstance(item, dict)
                ],
                schema=machine.telemetry_schema,
            )
            topics.append(
                MqttTopicConfig(
                    topic=str(raw["topic"]),
                    normalizer=normalizer,
                    qos=int(raw.get("qos", 0)),
                )
            )

        return cls(
            machine,
            host=str(data["host"]),
            port=int(data.get("port", 1883)),
            keepalive=int(data.get("keepalive", 60)),
            username=str(data["username"]) if data.get("username") else None,
            password=str(data["password"]) if data.get("password") else None,
            topics=topics,
            client=client,
        )

    def start(self) -> None:
        if self._running:
            return
        client = self._client or _new_client()
        self._client = client

        if self._username is not None:
            client.username_pw_set(self._username, self._password)

        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(self._host, self._port, self._keepalive)
        client.loop_start()
        self._running = True

    def stop(self) -> None:
        if not self._running or self._client is None:
            return
        self._client.loop_stop()
        self._client.disconnect()
        self._running = False

    def _on_connect(
        self,
        client: Any,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any = None,
    ) -> None:
        del userdata, flags, properties
        if int(reason_code) != 0:
            self.errors.append(f"MQTT_CONNECT_ERROR: {reason_code}")
            return
        for topic in self._topics:
            client.subscribe(topic.topic, qos=topic.qos)

    def _on_message(self, client: Any, userdata: Any, message: Any) -> None:
        del client, userdata
        try:
            payload = json.loads(bytes(message.payload).decode("utf-8"))
        except Exception as exc:
            self.errors.append(f"MQTT_PAYLOAD_ERROR[{message.topic}]: {exc}")
            return

        config = self._topic_config(str(message.topic))
        if config is None:
            return

        result = config.normalizer.normalize(
            payload,
            observed_at=datetime.now(timezone.utc),
            received_at=datetime.now(timezone.utc),
            source=f"mqtt:{message.topic}",
        )
        for observation in result.observations:
            self._machine.observe(observation)
        self.errors.extend(
            f"{issue.code}[{issue.target_path}]: {issue.message}"
            for issue in result.issues
        )

    def _topic_config(self, actual_topic: str) -> MqttTopicConfig | None:
        for config in self._topics:
            if _topic_matches(config.topic, actual_topic):
                return config
        return None


def _new_client() -> Any:
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:
        raise ImportError("paho-mqtt is required; install sense-mqtt") from exc
    return mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)


def _topic_matches(subscription: str, topic: str) -> bool:
    sub_parts = subscription.split("/")
    topic_parts = topic.split("/")
    for index, sub in enumerate(sub_parts):
        if sub == "#":
            return True
        if index >= len(topic_parts):
            return False
        if sub != "+" and sub != topic_parts[index]:
            return False
    return len(sub_parts) == len(topic_parts)
