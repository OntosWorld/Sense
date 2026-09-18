"""Example 04 — publish Sense context through the official peaqOS SDK.

Install from the repository root:

    pip install -e .
    pip install -e packages/Sense-peaq

For a real network submission configure PeaqosClient.from_env() as documented
by peaqOS, then replace FakePeaqClient below with that client.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sense_ai import ContextMachine, TelemetryObservation, capability, equals, gte
from sense_peaq import PeaqContextPublisher, to_market_context


class FakePeaqClient:
    """Small stand-in that shows exactly what Sense sends to submit_event()."""

    def submit_event(self, **kwargs):
        print("\npeaq Activity Event payload:")
        for key, value in kwargs.items():
            if key == "raw_data":
                print(f"  {key}: {value.decode('utf-8')}")
            else:
                print(f"  {key}: {value}")
        return "0xexampletx", bytes.fromhex("11" * 32)


def build_machine() -> ContextMachine:
    machine = ContextMachine(machine_ref="delivery-drone-01")
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
    machine.observe(
        TelemetryObservation(
            path="safety.estop",
            value=False,
            observed_at=now,
            source="plc",
            ttl_ms=1000,
        )
    )
    machine.observe(
        TelemetryObservation(
            path="battery.level_pct",
            value=74,
            observed_at=now,
            source="bms",
            ttl_ms=5000,
        )
    )
    machine.observe(
        TelemetryObservation(
            path="nav.gps_lock",
            value=True,
            observed_at=now,
            source="nav",
            ttl_ms=2000,
        )
    )
    return machine


def main() -> None:
    machine = build_machine()
    result = machine.evaluate("delivery.ready")
    print("delivery.ready:", result.status.value)

    transition = machine.last_transition("delivery.ready")
    if transition is None:
        raise RuntimeError("expected an initial capability transition")

    publisher = PeaqContextPublisher(FakePeaqClient(), machine_id=123)
    published = publisher.publish_transition(
        transition,
        machine_ref=machine.machine_ref,
    )
    print("tx hash:", published.tx_hash)
    print("data hash:", published.data_hash_hex)

    market_context = to_market_context(machine.snapshot())
    print("\nSense runtime context for market/application decisions:")
    print(market_context.to_dict())


if __name__ == "__main__":
    main()
