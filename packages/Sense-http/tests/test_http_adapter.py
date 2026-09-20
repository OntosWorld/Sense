"""HTTP polling adapter contract using a fake client.

The module name is adapter-specific so repository-wide pytest collection does
not collide with the MQTT adapter contract.
"""

from __future__ import annotations

from sense_ai import ContextMachine, TelemetryMapping, TelemetryNormalizer
from sense_http import HttpPollingAdapter


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self):
        return {"battery": {"pct": 76}}


class FakeClient:
    def __init__(self) -> None:
        self.calls = []
        self.closed = False

    def get(self, url, *, headers, timeout):
        self.calls.append((url, headers, timeout))
        return FakeResponse()

    def close(self):
        self.closed = True


def test_poll_once_feeds_machine() -> None:
    machine = ContextMachine()
    normalizer = TelemetryNormalizer(
        [
            TelemetryMapping(
                source_path="battery.pct",
                target_path="battery.level_pct",
            )
        ]
    )
    client = FakeClient()
    adapter = HttpPollingAdapter(
        machine,
        normalizer,
        url="http://robot.local/telemetry",
        client=client,
    )

    result = adapter.poll_once()

    assert result.ok
    observation = machine.get_observation("battery.level_pct")
    assert observation is not None
    assert observation.value == 76
    assert client.calls
