"""
End-to-end tests: simulator → telemetry → Sense → capability transition.

PRD §17.8 requires:
    Simulator
    → telemetry
    → Sense
    → capability transition
    → retrieve/confirm result

These tests are deterministic and require no network access.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sense_ai import (
    ContextMachine,
    TelemetryObservation,
    capability,
    equals,
    fresh,
    gte,
    lt,
)
from sense_ai.model.result import CapabilityStatus


class TestSimulatorPipeline:
    """
    Full pipeline: simulated sensor data → telemetry ingestion →
    Sense evaluation → capability transitions → result retrieval.
    """

    def test_simulated_battery_sensor_transitions(self) -> None:
        """
        Simulated battery sensor: values cross the threshold and trigger
        UNAVAILABLE → AVAILABLE transitions that can be observed and confirmed.
        """
        machine = ContextMachine(machine_ref="sim-robot-001")

        # Define the capability
        machine.define_capability(
            capability(
                "battery.operational",
                requires=[gte("battery.charge_pct", 20)],
            )
        )

        # 1. Simulator generates telemetry below threshold → UNAVAILABLE
        low_battery = TelemetryObservation(
            path="battery.charge_pct",
            value=15.0,
            observed_at=datetime.now(timezone.utc),
            source="sim:bms",
            ttl_ms=5000,
        )
        machine.observe(low_battery)
        result = machine.evaluate("battery.operational")
        assert result.status == CapabilityStatus.UNAVAILABLE
        assert len(result.blocking) == 1
        assert result.blocking[0].path == "battery.charge_pct"

        # 2. Simulator generates telemetry above threshold → AVAILABLE
        good_battery = TelemetryObservation(
            path="battery.charge_pct",
            value=85.0,
            observed_at=datetime.now(timezone.utc),
            source="sim:bms",
            ttl_ms=5000,
        )
        machine.observe(good_battery)
        result = machine.evaluate("battery.operational")
        assert result.status == CapabilityStatus.AVAILABLE
        assert result.blocking == []

        # 3. Transitions occurred — confirm via transition log
        transitions = machine.transitions("battery.operational")
        assert len(transitions) >= 2
        # Confirm the sequence
        statuses = [t.current for t in transitions]
        assert CapabilityStatus.UNAVAILABLE in statuses
        assert CapabilityStatus.AVAILABLE in statuses

    def test_stale_telemetry_triggers_unknown(self) -> None:
        """
        Telemetry older than the Fresh constraint's max_age_ms produces
        UNAVAILABLE → UNKNOWN transitions, confirming stale data is handled.
        """
        machine = ContextMachine(machine_ref="sim-robot-002")

        machine.define_capability(
            capability(
                "localization.valid",
                requires=[fresh("pose.age_ms", max_age_ms=2000)],
            )
        )

        # Stale telemetry
        old = datetime.now(timezone.utc) - timedelta(seconds=10)
        machine.observe("pose.age_ms", 500, observed_at=old)
        result = machine.evaluate("localization.valid")
        assert result.status == CapabilityStatus.UNKNOWN

        # Fresh telemetry
        now = datetime.now(timezone.utc)
        machine.observe("pose.age_ms", 500, observed_at=now)
        result = machine.evaluate("localization.valid")
        assert result.status == CapabilityStatus.AVAILABLE

    def test_multi_sensor_pipeline(self) -> None:
        """
        Simulator emits multiple sensors; all must satisfy their constraints
        for the capability to be AVAILABLE.
        """
        machine = ContextMachine(machine_ref="sim-robot-003")

        machine.define_capability(
            capability(
                "motor.operational",
                requires=[
                    equals("motor.enabled", True),
                    lt("motor.temp_c", 80.0),
                    gte("motor.speed_rpm", 0),
                ],
            )
        )

        # All sensors report healthy state
        now = datetime.now(timezone.utc)
        for path, value in [
            ("motor.enabled", True),
            ("motor.temp_c", 55.0),
            ("motor.speed_rpm", 1200),
        ]:
            machine.observe(
                TelemetryObservation(
                    path=path,
                    value=value,
                    observed_at=now,
                    source="sim:mcu",
                    ttl_ms=5000,
                )
            )

        result = machine.evaluate("motor.operational")
        assert result.status == CapabilityStatus.AVAILABLE

        # One sensor fails
        machine.observe("motor.temp_c", 95.0, observed_at=now)
        result = machine.evaluate("motor.operational")
        assert result.status == CapabilityStatus.UNAVAILABLE

        # Snapshot reflects the current state
        snap = machine.snapshot()
        assert snap.capabilities["motor.operational"].status == CapabilityStatus.UNAVAILABLE

    def test_transition_callback_in_pipeline(self) -> None:
        """
        The simulator registers a callback that fires on every capability
        transition, demonstrating the event-driven pipeline integration point.
        """
        machine = ContextMachine(machine_ref="sim-robot-004")

        machine.define_capability(
            capability("safety.active", requires=[equals("estop.released", True)])
        )

        events: list[str] = []

        @machine.on_transition("safety.active")
        def on_safety_change(transition):
            prev = transition.previous.value if transition.previous else "NONE"
            events.append(f"{prev}→{transition.current.value}")

        # Initial: UNKNOWN (no data)
        machine.evaluate("safety.active")
        # Release e-stop: UNKNOWN → AVAILABLE
        machine.observe("estop.released", True)
        machine.evaluate("safety.active")
        # Trigger e-stop: AVAILABLE → UNAVAILABLE
        machine.observe("estop.released", False)
        machine.evaluate("safety.active")

        assert len(events) >= 2
        assert any("AVAILABLE" in e for e in events)
        assert any("UNAVAILABLE" in e for e in events)

    def test_snapshot_retrieval_and_confirmation(self) -> None:
        """
        After the pipeline runs, a ContextSnapshot is retrievable and its
        contents match the last evaluation results.
        """
        machine = ContextMachine(
            machine_ref="sim-robot-005",
            peaq_did="did:peaq:sim-robot-005",
        )

        machine.define_capability(
            capability("network.ready", requires=[equals("network.up", True)])
        )
        machine.observe("network.up", True)
        machine.evaluate("network.ready")

        snap = machine.snapshot()
        assert snap.machine_ref == "sim-robot-005"
        assert snap.peaq_did == "did:peaq:sim-robot-005"
        assert snap.schema_version == "1.0"
        assert "network.ready" in snap.capabilities
        assert snap.capabilities["network.ready"].status == CapabilityStatus.AVAILABLE

        # Confirm the snapshot dict is serializable
        d = snap.to_dict()
        assert "machine" in d
        assert "capabilities" in d
        assert "observations" in d
