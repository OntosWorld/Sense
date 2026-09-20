"""End-to-end tests for Sense peaq integration boundaries."""

from __future__ import annotations

import json
import sys
import types
from unittest.mock import MagicMock

import pytest

from sense_ai import CapabilityStatus, ContextMachine, capability, equals, gte
from sense_ai.errors import (
    PeaqConfigurationError,
    PeaqNetworkError,
    UnsupportedPeaqFlowError,
)


@pytest.fixture
def peaq_constants(monkeypatch: pytest.MonkeyPatch) -> None:
    package = types.ModuleType("peaq_os_sdk")
    constants = types.ModuleType("peaq_os_sdk.constants")
    constants.EVENT_TYPE_ACTIVITY = 1
    monkeypatch.setitem(sys.modules, "peaq_os_sdk", package)
    monkeypatch.setitem(sys.modules, "peaq_os_sdk.constants", constants)


def _transitioning_machine(machine_ref: str = "robot-001") -> ContextMachine:
    machine = ContextMachine(machine_ref=machine_ref)
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
    def test_transition_is_submitted_as_self_reported_activity_event(
        self, peaq_constants: None
    ) -> None:
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
            snapshot=machine.snapshot().publishable_view(),
        )

        assert result.tx_hash == "0xabc123"
        assert result.data_hash_hex == "0x" + ("11" * 32)

        kwargs = client.submit_event.call_args.kwargs
        assert kwargs["machine_id"] == 42
        assert kwargs["event_type"] == 1
        assert kwargs["trust_level"] == 0
        assert kwargs["source_chain_id"] == 0
        assert kwargs["source_tx_hash"] is None
        assert kwargs["currency"] == ""

        payload = json.loads(kwargs["raw_data"].decode("utf-8"))
        assert payload["type"] == "sense.capability_transition"
        assert payload["transition"]["capability"] == "warehouse.pick"
        assert payload["transition"]["current"] == "UNAVAILABLE"
        assert all(
            "observed" not in reason for reason in payload["transition"]["reasons"]
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
        assert any("observed" in reason for reason in payload["transition"]["reasons"])

    def test_future_wall_clock_is_clamped_to_latest_chain_block(
        self, peaq_constants: None
    ) -> None:
        from sense_peaq import PeaqEventPublisher

        machine = _transitioning_machine()
        transition = machine.last_transition()
        assert transition is not None

        client = MagicMock()
        client.web3.eth.get_block.return_value = {"timestamp": 123}
        client.submit_event.return_value = ("0xtx", bytes.fromhex("44" * 32))

        PeaqEventPublisher(client, machine_id=1).publish_transition(transition)

        assert client.submit_event.call_args.kwargs["timestamp"] == 123

    def test_onchain_provenance_requires_transaction_hash(self) -> None:
        from sense_peaq import EventProvenance

        with pytest.raises(PeaqConfigurationError):
            EventProvenance(trust_level=1, source_chain_id=3338)

    def test_onchain_provenance_is_forwarded_to_sdk(self, peaq_constants: None) -> None:
        from sense_peaq import EventProvenance, PeaqEventPublisher

        machine = _transitioning_machine()
        transition = machine.last_transition()
        assert transition is not None

        client = MagicMock()
        client.submit_event.return_value = ("0xtx", bytes.fromhex("33" * 32))
        publisher = PeaqEventPublisher(client, machine_id=1)
        provenance = EventProvenance.onchain(
            source_chain_id=8453,
            source_tx_hash="0x" + ("12" * 32),
        )

        publisher.publish_transition(transition, provenance=provenance)

        kwargs = client.submit_event.call_args.kwargs
        assert kwargs["trust_level"] == 1
        assert kwargs["source_chain_id"] == 8453
        assert kwargs["source_tx_hash"] == "0x" + ("12" * 32)

    def test_hardware_signed_level_is_not_claimed_without_attestation(self) -> None:
        from sense_peaq import EventProvenance

        with pytest.raises(UnsupportedPeaqFlowError):
            EventProvenance(trust_level=2)

    def test_sdk_failure_becomes_typed_network_error(
        self, peaq_constants: None
    ) -> None:
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

    def test_market_eligibility_rejects_unavailable_machine(self) -> None:
        from sense_peaq import check_market_eligibility

        machine = _transitioning_machine()
        eligibility = check_market_eligibility(
            machine.snapshot(),
            ["warehouse.pick"],
        )

        assert not eligibility.eligible
        assert eligibility.rejected["warehouse.pick"] == "UNAVAILABLE"

    def test_market_candidate_filter_uses_caller_machine_ref(self) -> None:
        from sense_peaq import filter_market_candidates

        ready = ContextMachine(machine_ref="ready")
        ready.define_capability(
            capability("warehouse.pick", requires=[equals("gripper.ready", True)])
        )
        ready.observe("gripper.ready", True)

        blocked = _transitioning_machine(machine_ref="blocked")

        candidates = [
            {"machine": "ready", "service": "pick-a"},
            {"machine": "blocked", "service": "pick-b"},
        ]
        selected = filter_market_candidates(
            candidates,
            snapshots_by_machine={
                "ready": ready.snapshot(),
                "blocked": blocked.snapshot(),
            },
            required_capabilities=["warehouse.pick"],
            machine_ref=lambda item: item["machine"],
        )

        assert selected == [{"machine": "ready", "service": "pick-a"}]

    def test_adapter_delegates_to_official_orchestration_surface(self) -> None:
        from sense_peaq import MachineMarketsAdapter

        orchestration = MagicMock()
        orchestration.list_machines.return_value = {"items": [{"id": 42}]}
        orchestration.list_market_services.return_value = {"items": []}
        orchestration.get_market_service.return_value = {"item": {"id": "service-1"}}
        orchestration.search_market.return_value = {"searchId": "search-1"}
        orchestration.get_market_search.return_value = {"status": "completed"}

        client = MagicMock()
        client.orchestration = orchestration
        adapter = MachineMarketsAdapter(client)

        assert adapter.list_machines(limit=10)["items"][0]["id"] == 42
        adapter.list_market_services(limit=5)
        adapter.get_market_service("service-1")
        adapter.search_market({"request": "opaque-sdk-request"}, "pair-token")
        adapter.get_market_search("search-1")

        orchestration.list_machines.assert_called_once_with(limit=10, cursor=None)
        orchestration.list_market_services.assert_called_once_with(
            None, limit=5, cursor=None
        )
        orchestration.get_market_service.assert_called_once_with("service-1", None)
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
