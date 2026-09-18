"""End-to-end tests for Sense peaq integration boundaries."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock

import pytest

from sense_ai import CapabilityStatus, ContextMachine, capability, equals, gte
from sense_ai.errors import PeaqConfigurationError, PeaqNetworkError


@pytest.fixture
def peaq_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    package = types.ModuleType("peaq_os_sdk")
    constants = types.ModuleType("peaq_os_sdk.constants")
    constants.EVENT_TYPE_ACTIVITY = 1
    monkeypatch.setitem(sys.modules, "peaq_os_sdk", package)
    monkeypatch.setitem(sys.modules, "peaq_os_sdk.constants", constants)


def _transitioning_machine() -> ContextMachine:
    machine = ContextMachine(machine_ref="robot-001")
    machine.define_capability(
        capability(
            "warehouse.pick",
            requires=[
                gte("battery.level_pct", 20),
                equals("safety.estop", False),
            ],
        )
    )
    machine.observe("battery.level_pct", 80)
    machine.observe("safety.estop", False)
    machine.evaluate("warehouse.pick")
    machine.observe("battery.level_pct", 10)
    machine.evaluate("warehouse.pick")
    return machine


class TestPeaqActivityEvents:
    def test_transition_is_submitted_as_activity_event(self, peaq_constants: None) -> None:
        from sense_peaq import PeaqEventPublisher

        machine = _transitioning_machine()
        transition = machine.last_transition("warehouse.pick")
        assert transition is not None
        assert transition.current == CapabilityStatus.UNAVAILABLE

        client = MagicMock()
        client.submit_event.return_value = ("0xabc123", bytes.fromhex("11" * 32))

        publisher = PeaqEventPublisher(client, machine_id=42)
        result = publisher.publish_transition(
            transition,
            snapshot=machine.snapshot(),
        )

        assert result.tx_hash == "0xabc123"
        assert result.data_hash_hex == "0x" + ("11" * 32)

        kwargs = client.submit_event.call_args.kwargs
        assert kwargs["machine_id"] == 42
        assert kwargs["event_type"] == 1
        assert kwargs["trust_level"] == 0
        assert kwargs["source_chain_id"] == 0
        assert kwargs["currency"] == ""

        payload = json.loads(kwargs["raw_data"].decode("utf-8"))
        assert payload["type"] == "sense.capability_transition"
        assert payload["transition"]["capability"] == "warehouse.pick"
        assert payload["transition"]["current"] == "UNAVAILABLE"
        assert all(
            "observed" not in reason
            for reason in payload["transition"]["reasons"]
        )

    def test_transition_observed_values_require_explicit_opt_in(
        self, peaq_constants: None
    ) -> None:
        from sense_peaq import PeaqEventPublisher

        machine = _transitioning_machine()
        transition = machine.last_transition("warehouse.pick")
        assert transition is not None

        client = MagicMock()
        client.submit_event.return_value = ("0xabc123", bytes.fromhex("22" * 32))
        publisher = PeaqEventPublisher(client, machine_id=42)
        publisher.publish_transition(
            transition,
            include_observed_values=True,
        )

        payload = json.loads(
            client.submit_event.call_args.kwargs["raw_data"].decode("utf-8")
        )
        assert any(
            "observed" in reason
            for reason in payload["transition"]["reasons"]
        )

    def test_invalid_trust_level_is_rejected(self) -> None:
        from sense_peaq import PeaqEventPublisher

        with pytest.raises(PeaqConfigurationError):
            PeaqEventPublisher(MagicMock(), machine_id=1, trust_level=3)

    def test_sdk_failure_becomes_typed_network_error(self, peaq_constants: None) -> None:
        from sense_peaq import PeaqEventPublisher

        machine = _transitioning_machine()
        transition = machine.last_transition()
        assert transition is not None

        client = MagicMock()
        client.submit_event.side_effect = TimeoutError("rpc timeout")
        publisher = PeaqEventPublisher(client, machine_id=1)

        with pytest.raises(PeaqNetworkError) as exc_info:
            publisher.publish_transition(transition)

        assert exc_info.value.is_retryable is True


class TestMachineMarketsDelegation:
    def test_runtime_context_keeps_live_capability_state(self) -> None:
        from sense_peaq import to_market_context

        machine = _transitioning_machine()
        context = to_market_context(machine.snapshot())

        sense = context["sense"]
        assert sense["machine_ref"] == "robot-001"
        assert sense["capabilities"]["warehouse.pick"]["status"] == "UNAVAILABLE"
        assert "warehouse.pick" not in sense["currently_usable_capabilities"]

    def test_adapter_delegates_to_official_orchestration_surface(self) -> None:
        from sense_peaq import MachineMarketsAdapter

        orchestration = MagicMock()
        orchestration.list_machines.return_value = {"items": [{"id": 42}]}
        orchestration.list_market_services.return_value = {"items": []}
        orchestration.search_market.return_value = {"searchId": "search-1"}
        orchestration.get_market_search.return_value = {"status": "completed"}

        client = MagicMock()
        client.orchestration = orchestration
        adapter = MachineMarketsAdapter(client)

        assert adapter.list_machines(limit=10)["items"][0]["id"] == 42
        adapter.list_market_services(limit=5)
        adapter.search_market({"request": "opaque-sdk-request"}, "pair-token")
        adapter.get_market_search("search-1")

        orchestration.list_machines.assert_called_once_with(limit=10, cursor=None)
        orchestration.list_market_services.assert_called_once_with(
            None, limit=5, cursor=None
        )
        orchestration.search_market.assert_called_once_with(
            {"request": "opaque-sdk-request"}, "pair-token"
        )
        orchestration.get_market_search.assert_called_once_with("search-1")

    def test_missing_orchestration_is_configuration_error(self) -> None:
        from sense_peaq import MachineMarketsAdapter

        client = MagicMock()
        client.orchestration = None

        with pytest.raises(PeaqConfigurationError):
            MachineMarketsAdapter(client)
