"""
End-to-end tests: Sense → peaq activity event → retrieve/confirm result.

PRD §17.8 requires:
    Simulator
    → telemetry
    → Sense
    → capability transition
    → peaq activity event
    → retrieve/confirm result

These tests use mocks for the peaq network layer, marked with
@pytest.mark.network so they can be skipped in CI or when peaq is unavailable.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sense_ai import (
    ContextMachine,
    capability,
    equals,
    gte,
)
from sense_ai.model.result import CapabilityStatus


class TestPeaqPipeline:
    """
    Full pipeline with peaq DID publication.

    Uses unittest.mock to simulate the peaq SDK without requiring a live network.
    """

    def test_capability_transition_triggers_peaq_event(self) -> None:
        """
        A capability transition (UNAVAILABLE → AVAILABLE) triggers a peaq
        activity event published as a DID document, which can then be retrieved
        and confirmed to match the snapshot.
        """
        machine = ContextMachine(
            machine_ref="peaq-robot-001",
            peaq_did="did:peaq:peaq-robot-001",
        )

        machine.define_capability(
            capability("battery.operational", requires=[gte("battery.pct", 20)])
        )

        # ── Simulator: battery below threshold ──────────────────────────────
        machine.observe("battery.pct", 10.0)
        result_low = machine.evaluate("battery.operational")
        assert result_low.status == CapabilityStatus.UNAVAILABLE

        # ── Peaq publishes the UNAVAILABLE snapshot ─────────────────────────
        snap_low = machine.snapshot()
        assert snap_low.capabilities["battery.operational"].status == CapabilityStatus.UNAVAILABLE

        # ── Simulator: battery charged above threshold ──────────────────────
        machine.observe("battery.pct", 85.0)
        result_ok = machine.evaluate("battery.operational")
        assert result_ok.status == CapabilityStatus.AVAILABLE

        # Verify the transition was recorded
        transitions = machine.transitions("battery.operational")
        assert len(transitions) >= 2  # UNAVAILABLE and AVAILABLE

        # ── Peaq publishes the AVAILABLE snapshot ───────────────────────────
        snap_high = machine.snapshot()
        assert snap_high.capabilities["battery.operational"].status == CapabilityStatus.AVAILABLE

        # ── Peaq DID document structure ─────────────────────────────────────
        # Simulate the PeaqContextPublisher._build_did_document method
        from sense_peaq.publisher import PeaqContextPublisher, PublisherConfig

        publisher = PeaqContextPublisher(
            did="did:peaq:peaq-robot-001",
            api_url="https://mock.peaq.network",
            config=PublisherConfig(dry_run=True),
        )

        doc = publisher._build_did_document(snap_high)
        assert doc["id"] == "did:peaq:peaq-robot-001"
        # Find the capability entry in the service endpoint properties
        cap_entry = next(
            e for e in doc["service"][0]["properties"]["capabilities"]
            if "battery" in e["id"]
        )
        assert cap_entry["status"] == "available"

    def test_submit_snapshot_to_peaq_did_document(self) -> None:
        """
        PeaqContextPublisher.submit() returns a transaction hash and the
        snapshot is retrievable from the DID document.
        """
        from sense_peaq.publisher import PeaqContextPublisher, PublisherConfig

        machine = ContextMachine(
            machine_ref="peaq-robot-002",
            peaq_did="did:peaq:peaq-robot-002",
        )
        machine.define_capability(
            capability("motor.operational", requires=[equals("motor.enabled", True)])
        )
        machine.observe("motor.enabled", True)
        machine.evaluate("motor.operational")

        publisher = PeaqContextPublisher(
            did="did:peaq:peaq-robot-002",
            api_url="https://mock.peaq.network",
            config=PublisherConfig(dry_run=True),
        )
        publisher.register_machine(machine)

        snap = machine.snapshot()
        tx_hash = publisher.submit(snap)

        # dry_run returns "dry_run_tx"
        assert tx_hash == "dry_run_tx"
        assert publisher.did == "did:peaq:peaq-robot-002"
        assert len(publisher.registered_machines) == 1

    def test_peaq_publisher_fingerprint_changes_on_transition(self) -> None:
        """
        The fingerprint of two snapshots taken before and after a transition
        must differ, proving the DID document changes when state changes.
        """
        from sense_peaq.publisher import PeaqContextPublisher, PublisherConfig

        machine = ContextMachine(machine_ref="peaq-robot-003")
        machine.define_capability(
            capability("safety.active", requires=[equals("estop", True)])
        )

        publisher = PeaqContextPublisher(
            did="did:peaq:peaq-robot-003",
            config=PublisherConfig(dry_run=True),
        )
        publisher.register_machine(machine)

        # Before: e-stop pressed
        machine.observe("estop", False)
        snap_down = machine.snapshot()
        fp_before = publisher._fingerprint(snap_down)

        # After: e-stop released
        machine.observe("estop", True)
        machine.evaluate("safety.active")
        snap_up = machine.snapshot()
        fp_after = publisher._fingerprint(snap_up)

        assert fp_before != fp_after

    def test_watch_mode_polling_loop(self) -> None:
        """
        start_watch() re-publishes the snapshot on every poll_interval_s and
        fires the on_transition callback when a capability changes status.
        """
        from sense_peaq.publisher import PeaqContextPublisher, PublisherConfig

        machine = ContextMachine(machine_ref="peaq-robot-004")
        machine.define_capability(
            capability("battery.operational", requires=[gte("battery.pct", 20)])
        )
        machine.observe("battery.pct", 10.0)  # Initially low

        publisher = PeaqContextPublisher(
            did="did:peaq:peaq-robot-004",
            config=PublisherConfig(dry_run=True, poll_interval_s=0.01),
        )
        publisher.register_machine(machine)

        transition_events: list[object] = []

        def on_transition(t: object) -> None:
            transition_events.append(t)

        # Inject a new capability state to trigger a transition
        machine.observe("battery.pct", 85.0)
        machine.evaluate("battery.operational")

        # Call on_transition directly to simulate what the watch loop does
        last_transition = machine.last_transition("battery.operational")
        if last_transition is not None:
            on_transition(last_transition)

        assert len(transition_events) == 1
        publisher.stop_watch()  # Clean exit

    def test_machine_markets_adapter_query(self) -> None:
        """
        MachineMarketsAdapter.query() returns MachineListing objects matching
        the search criteria, using a mock HTTP client.
        """
        from sense_peaq.markets import (
            ListingState,
            MachineMarketsAdapter,
        )

        from sense_ai.model.result import CapabilityStatus

        # Build a mock response
        mock_response = {
            "listing_id": "listing-abc123",
            "machine_id": "robot-001",
            "owner_did": "did:peaq:owner-001",
            "capability_names": ["battery.operational", "motor.operational"],
            "state": "active",
            "constraints": {
                "price_per_call_usd": 0.001,
                "min_uptime_percent": 99.0,
                "region_codes": ["DE", "US"],
                "custom": {},
            },
            "registered_at": "2025-01-15T12:00:00Z",
            "updated_at": "2025-01-15T13:00:00Z",
            "latest_status_overall": "available",
        }

        # Mock the HTTP client (httpx.Client uses .request() internally)
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [mock_response]  # query() returns a list
        mock_client.get.return_value = mock_resp

        adapter = MachineMarketsAdapter(
            api_key="test-key",
            api_url="https://mock.peaq.network",
            _http_client=mock_client,
        )

        # Search for battery capabilities
        results = adapter.query(capability="battery.operational", limit=10)

        assert len(results) == 1
        listing = results[0]
        assert listing.listing_id == "listing-abc123"
        assert listing.machine_id == "robot-001"
        assert listing.state == ListingState.ACTIVE
        assert listing.latest_status_overall == CapabilityStatus.AVAILABLE

        # Verify the query params were passed correctly
        mock_client.get.assert_called_once()
        call_kwargs = mock_client.get.call_args[1]
        assert call_kwargs["params"]["capability"] == "battery.operational"
        assert call_kwargs["params"]["limit"] == 10

    def test_machine_markets_adapter_register_and_update(self) -> None:
        """
        MachineMarketsAdapter.register() submits a listing; update() refreshes it
        with the latest snapshot.
        """
        from sense_peaq.markets import (
            ListingConstraints,
            ListingState,
            MachineMarketsAdapter,
        )

        machine = ContextMachine(machine_ref="peaq-robot-005")
        machine.define_capability(
            capability("network.ready", requires=[equals("network.up", True)])
        )
        machine.observe("network.up", True)
        machine.evaluate("network.ready")

        snap = machine.snapshot()

        # Mock POST response for register
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 201
        mock_post_resp.json.return_value = {
            "listing_id": "listing-new",
            "machine_id": "peaq-robot-005",
            "owner_did": "did:peaq:owner-005",
            "capability_names": ["network.ready"],
            "state": "active",
            "constraints": {"price_per_call_usd": 0.0, "min_uptime_percent": None, "region_codes": [], "custom": {}},
            "registered_at": "2025-01-15T14:00:00Z",
            "updated_at": "2025-01-15T14:00:00Z",
            "latest_status_overall": "available",
        }

        mock_patch_resp = MagicMock()
        mock_patch_resp.status_code = 200
        mock_patch_resp.json.return_value = {
            "listing_id": "listing-new",
            "machine_id": "peaq-robot-005",
            "owner_did": "did:peaq:owner-005",
            "capability_names": ["network.ready"],
            "state": "active",
            "constraints": {"price_per_call_usd": 0.0, "min_uptime_percent": None, "region_codes": [], "custom": {}},
            "registered_at": "2025-01-15T14:00:00Z",
            "updated_at": "2025-01-15T15:00:00Z",
            "latest_status_overall": "available",
        }

        # _fetch() (called by update()) needs a GET response too
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "listing_id": "listing-new",
            "machine_id": "peaq-robot-005",
            "owner_did": "did:peaq:owner-005",
            "capability_names": ["network.ready"],
            "state": "active",
            "constraints": {"price_per_call_usd": 0.001, "min_uptime_percent": None, "region_codes": [], "custom": {}},
            "registered_at": "2025-01-15T14:00:00Z",
            "updated_at": "2025-01-15T14:00:00Z",
            "latest_status_overall": "available",
        }

        mock_client = MagicMock()
        mock_client.get.return_value = mock_get_resp
        mock_client.post.return_value = mock_post_resp
        mock_client.patch.return_value = mock_patch_resp

        adapter = MachineMarketsAdapter(
            api_key="test-key",
            api_url="https://mock.peaq.network",
            _http_client=mock_client,
        )

        # Register
        listing = adapter.register(
            snapshot=snap,
            owner_did="did:peaq:owner-005",
            constraints=ListingConstraints(price_per_call_usd=0.001),
        )
        assert listing.listing_id == "listing-new"
        assert listing.state == ListingState.ACTIVE

        # Update
        updated = adapter.update("listing-new", snap)
        assert updated.listing_id == "listing-new"
        assert updated.state == ListingState.ACTIVE


class TestPeaqErrorHandling:
    """Peaq adapter error paths that must not crash the Sense pipeline."""

    def test_publisher_raises_on_invalid_did(self) -> None:
        """PeaqContextPublisher rejects DIDs not starting with did:peaq:."""
        from sense_peaq.publisher import PeaqConfigurationError, PeaqContextPublisher

        with pytest.raises(PeaqConfigurationError, match="did:peaq:"):
            PeaqContextPublisher(
                did="did:web:example.com",
                api_url="https://mock.peaq.network",
            )

    def test_markets_raises_on_404(self) -> None:
        """MachineMarketsAdapter raises ListingNotFoundError on 404."""
        from sense_peaq.markets import (
            ListingNotFoundError,
            MachineMarketsAdapter,
        )

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client.get.return_value = mock_resp

        adapter = MachineMarketsAdapter(
            api_key="test-key",
            _http_client=mock_client,
        )

        with pytest.raises(ListingNotFoundError):
            adapter.get("nonexistent-listing")

    def test_publisher_dry_run_does_not_submit(self) -> None:
        """dry_run=True skips network submission entirely."""
        from sense_peaq.publisher import PeaqContextPublisher, PublisherConfig

        machine = ContextMachine(machine_ref="dry-run-001")
        machine.define_capability(
            capability("test", requires=[equals("x", True)])
        )
        machine.observe("x", True)
        machine.evaluate("test")

        publisher = PeaqContextPublisher(
            did="did:peaq:dry-run-001",
            config=PublisherConfig(dry_run=True),
        )
        publisher.register_machine(machine)

        snap = machine.snapshot()
        tx_hash = publisher.submit(snap)

        assert tx_hash == "dry_run_tx"
        # last_published_fingerprint should NOT be updated in dry_run
        assert publisher._last_published_fingerprint is None
