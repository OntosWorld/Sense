"""Contract-style tests for the optional peaq adapter.

These tests exercise Sense against the documented peaqOS Python SDK surface.
They require the optional peaq-os-sdk dependency and do not make live network
requests.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from sense_ai import ContextMachine, CapabilityStatus, capability, equals, gte

peaq_os_sdk = pytest.importorskip("peaq_os_sdk")

from sense_peaq import MachineMarketsAdapter, PeaqContextPublisher, to_market_context


class TestPeaqActivityEvents:
    def test_transition_is_submitted_as_activity_event(self) -> None:
        machine = ContextMachine(machine_ref="peaq-robot-001")
        machine.define_capability(
            capability("battery.operational", requires=[gte("battery.pct", 20)])
        )

        machine.observe("battery.pct", 10.0)
        machine.evaluate("battery.operational")
        machine.observe("battery.pct", 85.0)
        result = machine.evaluate("battery.operational")
        assert result.status == CapabilityStatus.AVAILABLE

        transition = machine.last_transition("battery.operational")
        assert transition is not None

        client = MagicMock()
        client.submit_event.return_value = ("0xtx", bytes.fromhex("11" * 32))

        publisher = PeaqContextPublisher(client, machine_id=123)
        published = publisher.publish_transition(
            transition,
            machine_ref=machine.machine_ref,
        )

        assert published.tx_hash == "0xtx"
        assert published.data_hash_hex == "11" * 32
        kwargs = client.submit_event.call_args.kwargs
        assert kwargs["event_type"] == peaq_os_sdk.EVENT_TYPE_ACTIVITY
        assert kwargs["value"] == 0
        assert kwargs["currency"] == ""
        assert kwargs["trust_level"] == peaq_os_sdk.TRUST_SELF_REPORTED
        assert b"sense.capability.transition" in kwargs["raw_data"]

    def test_snapshot_excludes_observations_by_default(self) -> None:
        machine = ContextMachine(machine_ref="peaq-robot-002")
        machine.define_capability(
            capability("motor.operational", requires=[equals("motor.enabled", True)])
        )
        machine.observe("motor.enabled", True)
        snapshot = machine.snapshot()

        client = MagicMock()
        client.submit_event.return_value = ("0xtx", bytes.fromhex("22" * 32))
        publisher = PeaqContextPublisher(client, machine_id=456)
        publisher.publish_snapshot(snapshot)

        raw_data = client.submit_event.call_args.kwargs["raw_data"]
        assert b"motor.operational" in raw_data
        assert b'"observations":[]' in raw_data


class TestMachineMarketsAdapter:
    def test_delegates_to_official_orchestration_namespace(self) -> None:
        orchestration = MagicMock()
        orchestration.list_machines.return_value = SimpleNamespace(items=(), next_cursor=None)
        orchestration.list_market_services.return_value = SimpleNamespace(
            items=(), next_cursor=None
        )

        client = MagicMock()
        client.orchestration = orchestration
        adapter = MachineMarketsAdapter(client)

        adapter.list_machines(limit=10)
        adapter.list_market_services(limit=10)

        orchestration.list_machines.assert_called_once_with(limit=10, cursor=None)
        orchestration.list_market_services.assert_called_once_with(
            None, limit=10, cursor=None
        )

    def test_market_context_is_local_runtime_context(self) -> None:
        machine = ContextMachine(machine_ref="robot-003")
        machine.define_capability(
            capability("warehouse.pick", requires=[equals("gripper.ready", True)])
        )
        machine.observe("gripper.ready", True)

        context = to_market_context(machine.snapshot())

        assert context.machine_ref == "robot-003"
        assert context.capabilities["warehouse.pick"] == "AVAILABLE"
