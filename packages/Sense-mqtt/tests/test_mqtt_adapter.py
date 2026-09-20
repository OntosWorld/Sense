"""MQTT adapter contract using a fake paho client.

The module name is adapter-specific so repository-wide pytest collection does
not collide with the HTTP adapter contract.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from sense_ai import ContextMachine, TelemetryFieldSpec
from sense_mqtt import MqttSenseAdapter


class FakeClient:
    def __init__(self) -> None:
        self.on_connect = None
        self.on_message = None
        self.subscriptions = []
        self.connected = None
        self.running = False

    def username_pw_set(self, username, password=None):
        self.credentials = (username, password)

    def connect(self, host, port, keepalive):
        self.connected = (host, port, keepalive)

    def loop_start(self):
        self.running = True

    def loop_stop(self):
        self.running = False

    def disconnect(self):
        self.connected = None

    def subscribe(self, topic, qos=0):
        self.subscriptions.append((topic, qos))


def test_mqtt_json_payload_is_normalized() -> None:
    machine = ContextMachine()
    machine.define_observation(
        TelemetryFieldSpec("battery.level_pct", kind="number")
    )
    client = FakeClient()
    adapter = MqttSenseAdapter.from_dict(
        machine,
        {
            "host": "broker.local",
            "topics": [
                {
                    "topic": "robot/+/telemetry",
                    "qos": 1,
                    "mappings": [
                        {
                            "source": "battery",
                            "target": "battery.level_pct",
                            "transform": "ratio_to_percent",
                        }
                    ],
                }
            ],
        },
        client=client,
    )

    adapter.start()
    adapter._on_connect(client, None, None, 0)
    assert ("robot/+/telemetry", 1) in client.subscriptions

    message = SimpleNamespace(
        topic="robot/7/telemetry",
        payload=json.dumps({"battery": 0.84}).encode("utf-8"),
    )
    adapter._on_message(client, None, message)

    observation = machine.get_observation("battery.level_pct")
    assert observation is not None
    assert observation.value == 84.0
    adapter.stop()
