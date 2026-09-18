"""
peaq integration: publish a capability snapshot as a signed DID document
update on the peaq network, and query the Machine Markets listing registry.

Note: this example uses a mock peaq client when RPC_ENDPOINT is not set.
Set RPC_ENDPOINT and a real peaq client to exercise real on-chain publishing.

Run from the repo root::

    RPC_ENDPOINT=https://api.peaq.network \\
    PYTHONPATH=src:packages/Sense-peaq/src python examples/04_peaq/evaluate.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sense_ai import (
    ContextMachine,
    TelemetryObservation,
    capability,
    gte,
    equals,
)
from sense_ai.errors import PeaqNetworkError, PeaqConfigurationError
from sense_peaq import PeaqContextPublisher, MachineMarketsAdapter
from sense_peaq.publisher import PublisherConfig


# ── Mock HTTP client for Machine Markets ──────────────────────────────────────

class _MockHttpClient:
    """Minimal mock that satisfies MachineMarketsAdapter._rpc without hitting a live API."""

    def get(self, url: str, **kwargs: Any) -> Any:
        class _resp:
            status_code = 200
            def json(self) -> Any:
                return [
                    {
                        "listing_id": "0xLIST001",
                        "machine_id": "did:peaq:0xAAAA",
                        "owner_did": "did:peaq:0xOWNER1",
                        "capability_names": ["warehouse.pick"],
                        "state": "active",
                        "constraints": {"price_per_call_usd": 0.001, "region_codes": ["eu-west-1"]},
                        "registered_at": "2025-01-01T00:00:00Z",
                        "updated_at": "2025-01-15T09:00:00Z",
                        "latest_status_overall": "AVAILABLE",
                    },
                    {
                        "listing_id": "0xLIST002",
                        "machine_id": "did:peaq:0xBBBB",
                        "owner_did": "did:peaq:0xOWNER2",
                        "capability_names": ["warehouse.pick"],
                        "state": "active",
                        "constraints": {"price_per_call_usd": 0.002, "region_codes": ["us-east-1"]},
                        "registered_at": "2025-01-02T00:00:00Z",
                        "updated_at": "2025-01-15T09:05:00Z",
                        "latest_status_overall": "DEGRADED",
                    },
                ]
        return _resp()


# ── helpers ───────────────────────────────────────────────────────────────────

def _build_machine() -> ContextMachine:
    machine = ContextMachine(
        machine_ref="delivery-drone-01",
        peaq_did="did:peaq:0xREAL000000000000000001",
    )

    machine.define_capability(
        capability(
            "delivery.ready",
            version="1.0",
            requires=[
                equals("safety.estop", False),
                gte("battery.level_pct", 30),
                equals("nav.gps_lock", True),
            ],
            degrade_when=[
                gte("battery.level_pct", 50),  # degrade if above 50% (idle drain)
            ],
        )
    )

    now = datetime.now(timezone.utc)
    for obs in [
        TelemetryObservation(path="safety.estop",   value=False,      observed_at=now, source="plc",  ttl_ms=1000),
        TelemetryObservation(path="battery.level_pct", value=74,      observed_at=now, source="bms",  ttl_ms=2000),
        TelemetryObservation(path="nav.gps_lock",     value=True,      observed_at=now, source="nav",  ttl_ms=5000),
    ]:
        machine.observe(obs)

    return machine


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # ── 1. Build and snapshot the machine ─────────────────────────────────────

    machine = _build_machine()
    snapshot = machine.snapshot()

    print(f"\n{'─' * 60}")
    print(f"  Machine: {snapshot.machine_ref}")
    print(f"  peaq DID: {machine.peaq_did or '(not set)'}")
    print(f"  Schema: {snapshot.schema_version}")
    print(f"  Capabilities: {list(snapshot.capabilities.keys())}")

    # ── 2. Publish to peaq ─────────────────────────────────────────────────────
    # Use dry_run=True so PeaqContextPublisher builds and signs the DID document
    # without requiring a live peaq SDK or RPC endpoint.

    publisher = PeaqContextPublisher(
        did=machine.peaq_did,
        api_url="https://peaq.network/api/v1",
        signing_key_ref="keystore://default",
        config=PublisherConfig(dry_run=True),
    )
    publisher.register_machine(machine)

    print(f"\n{'─' * 60}")
    print(f"  Publishing to peaq (dry-run)…")

    try:
        tx_hash = publisher.submit(snapshot)
        print(f"  ✅ Published successfully")
        print(f"     tx_hash  : {tx_hash}")
    except PeaqConfigurationError as e:
        print(f"  ⚠️  Configuration error: {e}")
    except PeaqNetworkError as e:
        print(f"  ❌ Network error: {e}")

    # ── 3. Query Machine Markets ───────────────────────────────────────────────

    markets = MachineMarketsAdapter(_http_client=_MockHttpClient())

    print(f"\n{'─' * 60}")
    print(f"  Querying Machine Markets…")

    listings = markets.query(capability="warehouse.pick")
    print(f"  Found {len(listings)} listing(s):")

    for listing in listings:
        print(f"    [{listing.state.value:<12}]  {listing.machine_id}")
        print(f"      capability : {', '.join(listing.capability_names)}")
        print(f"      listing_id : {listing.listing_id}")
        print(f"      registered : {listing.registered_at}")
        print(f"      status     : {listing.latest_status_overall}")


if __name__ == "__main__":
    main()
