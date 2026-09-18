"""Opt-in live peaq Activity Event verification.

This file is intentionally excluded from normal CI. It performs a real
transaction only when SENSE_RUN_LIVE_PEAQ=1 is explicitly set.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SENSE_RUN_LIVE_PEAQ") != "1",
    reason="set SENSE_RUN_LIVE_PEAQ=1 to run live peaq verification",
)


def test_live_peaq_activity_event() -> None:
    from dotenv import load_dotenv
    from peaq_os_sdk import PeaqosClient
    from sense_ai import ContextMachine, capability, gte
    from sense_peaq import PeaqEventPublisher

    load_dotenv()

    raw_machine_id = os.getenv("SENSE_PEAQ_MACHINE_ID")
    if not raw_machine_id:
        pytest.fail("SENSE_PEAQ_MACHINE_ID is required for live verification")
    machine_id = int(raw_machine_id)

    machine = ContextMachine(machine_ref=f"peaq:{machine_id}")
    machine.define_capability(
        capability("sense.live.check", requires=[gte("battery.level_pct", 20)])
    )
    machine.observe("battery.level_pct", 80)
    machine.evaluate("sense.live.check")
    machine.observe("battery.level_pct", 10)
    machine.evaluate("sense.live.check")

    transition = machine.last_transition("sense.live.check")
    assert transition is not None

    client = PeaqosClient.from_env()
    publisher = PeaqEventPublisher(client, machine_id=machine_id)
    result = publisher.publish_transition(
        transition,
        snapshot=machine.snapshot().publishable_view(),
        metadata={"verification": "sense-live-test"},
    )

    assert result.tx_hash
    assert result.data_hash
