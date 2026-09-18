"""peaq adapter example using the current Sense integration boundaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sense_ai import ContextMachine, TelemetryObservation, capability, equals, gte
from sense_peaq import MachineMarketsAdapter, PeaqEventPublisher, to_market_context


class FakePeaqClient:
    """Small local stand-in for the official PeaqosClient surface."""

    def __init__(self) -> None:
        self.orchestration = FakeOrchestration()

    def submit_event(self, **kwargs: Any) -> tuple[str, bytes]:
        print("\nActivity Event request")
        print("  machine_id:", kwargs["machine_id"])
        print("  event_type:", kwargs["event_type"])
        print("  trust_level:", kwargs["trust_level"])
        print("  source_chain_id:", kwargs["source_chain_id"])
        print("  raw_data:", kwargs["raw_data"].decode("utf-8"))
        return "0xexample", bytes.fromhex("11" * 32)


class FakeOrchestration:
    def list_machines(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return {"items": [{"id": 42, "name": "demo-machine"}], "cursor": cursor}

    def list_market_services(
        self,
        options: Any = None,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        return {"items": [], "cursor": cursor}


def build_machine() -> ContextMachine:
    machine = ContextMachine(machine_ref="delivery-robot-01")
    machine.define_capability(
        capability(
            "delivery.ready",
            requires=[
                equals("safety.estop", False),
                gte("battery.level_pct", 30),
                equals("nav.gps_lock", True),
            ],
        )
    )

    now = datetime.now(timezone.utc)
    for observation in [
        TelemetryObservation(
            path="safety.estop",
            value=False,
            observed_at=now,
            source="plc",
            ttl_ms=1000,
        ),
        TelemetryObservation(
            path="battery.level_pct",
            value=74,
            observed_at=now,
            source="bms",
            ttl_ms=2000,
        ),
        TelemetryObservation(
            path="nav.gps_lock",
            value=True,
            observed_at=now,
            source="nav",
            ttl_ms=5000,
        ),
    ]:
        machine.observe(observation)

    machine.evaluate("delivery.ready")

    machine.observe("battery.level_pct", 10)
    machine.evaluate("delivery.ready")
    return machine


def main() -> None:
    machine = build_machine()
    transition = machine.last_transition("delivery.ready")
    assert transition is not None

    client = FakePeaqClient()

    publisher = PeaqEventPublisher(
        client,
        machine_id=42,
    )

    result = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
    )

    print("\nPublish result")
    print("  tx_hash:", result.tx_hash)
    print("  data_hash:", result.data_hash_hex)

    markets = MachineMarketsAdapter(client)
    print("\nMachines:", markets.list_machines(limit=10))

    runtime_context = to_market_context(machine.snapshot())
    print("\nSense runtime context:", runtime_context)


if __name__ == "__main__":
    main()
