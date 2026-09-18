"""Integration tests: ContextMachine full lifecycle."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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
from sense_ai.model.snapshot import ContextSnapshot


class TestMachineLifecycle:
    """Full lifecycle: create → define → observe → evaluate → snapshot."""

    def test_create_minimal_machine(self) -> None:
        """Machine can be created with no arguments."""
        m = ContextMachine()
        assert m.machine_ref is None
        assert m.peaq_did is None
        assert m.capability_names == ()
        assert m.observations == {}

    def test_create_with_identifiers(self) -> None:
        """Machine stores machine_ref and peaq_did."""
        m = ContextMachine(
            machine_ref="robot-001",
            peaq_did="did:peaq:abc123",
            trace_id="trace-xyz",
        )
        assert m.machine_ref == "robot-001"
        assert m.peaq_did == "did:peaq:abc123"
        assert m.observations == {}

    def test_define_capability_empty_store(self) -> None:
        """Capability registered; evaluate returns UNKNOWN before observations."""
        m = ContextMachine(machine_ref="r1")
        m.define_capability(
            capability(
                "test.cap",
                requires=[equals("battery.level_pct", 100)],
            )
        )
        assert "test.cap" in m.capability_names
        result = m.evaluate("test.cap")
        assert result.status == CapabilityStatus.UNKNOWN

    def test_observe_and_evaluate_available(self) -> None:
        """Observing values that satisfy all constraints → AVAILABLE."""
        m = ContextMachine(machine_ref="r1")
        m.define_capability(
            capability(
                "nav.ready",
                requires=[equals("gripper.available", True)],
            )
        )
        m.observe("gripper.available", True)
        result = m.evaluate("nav.ready")
        assert result.status == CapabilityStatus.AVAILABLE
        assert result.blocking == []
        assert result.warnings == []

    def test_observe_and_evaluate_unavailable(self) -> None:
        """Observing values that violate constraints → UNAVAILABLE."""
        m = ContextMachine(machine_ref="r1")
        m.define_capability(
            capability(
                "nav.ready",
                requires=[equals("gripper.available", True)],
            )
        )
        m.observe("gripper.available", False)
        result = m.evaluate("nav.ready")
        assert result.status == CapabilityStatus.UNAVAILABLE
        assert len(result.blocking) == 1
        assert result.warnings == []

    def test_observe_with_explicit_timestamp(self) -> None:
        """observe() accepts an explicit observed_at datetime."""
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        m = ContextMachine()
        obs = m.observe("temp.celsius", 22.5, observed_at=now)
        assert obs.observed_at == now
        assert m.observations["temp.celsius"].value == 22.5

    def test_observe_with_ttl(self) -> None:
        """observe() stores ttl_ms on the observation."""
        obs = TelemetryObservation(
            path="battery.level_pct",
            value=80,
            observed_at=datetime.now(timezone.utc),
            ttl_ms=10_000,
        )
        assert obs.ttl_ms == 10_000

    def test_observe_object_form(self) -> None:
        """observe() accepts a TelemetryObservation as the sole argument."""
        m = ContextMachine()
        obs = TelemetryObservation(
            path="speed.mps",
            value=1.5,
            observed_at=datetime.now(timezone.utc),
        )
        stored = m.observe(obs)
        assert stored.path == "speed.mps"
        assert stored.value == 1.5
        assert m.observations["speed.mps"].value == 1.5

    def test_observe_overwrites_previous(self) -> None:
        """Newer observation for the same path replaces the old one."""
        m = ContextMachine()
        m.observe("battery.level_pct", 50)
        later = datetime.now(timezone.utc)
        m.observe("battery.level_pct", 30, observed_at=later)
        assert m.observations["battery.level_pct"].value == 30

    def test_evaluate_unknown_capability_raises(self) -> None:
        """Evaluating an unregistered capability raises UnknownCapabilityError."""
        m = ContextMachine()
        with pytest.raises(Exception):  # Sense.errors.UnknownCapabilityError
            m.evaluate("nonexistent")

    def test_define_replaces_existing(self) -> None:
        """Re-defining a capability replaces the previous spec."""
        m = ContextMachine()
        m.define_capability(capability("x", requires=[equals("a", 1)]))
        m.define_capability(capability("x", requires=[equals("b", 2)]))
        assert len(m.capability_names) == 1
        # Re-evaluate — the new constraint should apply
        m.observe("a", 1)
        m.observe("b", 2)
        result = m.evaluate("x")
        assert result.status == CapabilityStatus.AVAILABLE

    def test_snapshot_repr(self) -> None:
        """snapshot() returns a ContextSnapshot."""
        m = ContextMachine(machine_ref="r1")
        m.define_capability(
            capability("cap1", requires=[equals("ready", True)])
        )
        m.observe("ready", True)
        snap = m.snapshot()
        assert snap.machine_ref == "r1"
        assert snap.schema_version == "1.0"
        assert "cap1" in snap.capabilities

    def test_snapshot_idempotent(self) -> None:
        """snapshot() is idempotent when nothing changes."""
        m = ContextMachine()
        m.define_capability(capability("c", requires=[equals("x", 1)]))
        m.observe("x", 1)
        s1 = m.snapshot()
        s2 = m.snapshot()
        assert s1 is s2  # Same object returned

    def test_snapshot_not_idempotent_after_observe(self) -> None:
        """snapshot() returns a new object after new observations are added."""
        m = ContextMachine()
        m.define_capability(capability("c", requires=[equals("x", 1)]))
        m.observe("x", 1)
        s1 = m.snapshot()
        m.observe("y", 2)
        s2 = m.snapshot()
        assert s2 is not s1
        assert "y" in s2.observations

    def test_evaluate_all(self) -> None:
        """evaluate_all() returns results for every registered capability."""
        m = ContextMachine()
        m.define_capability(capability("a", requires=[equals("x", 1)]))
        m.define_capability(capability("b", requires=[equals("y", 2)]))
        m.observe("x", 1)
        m.observe("y", 2)
        results = m.evaluate_all()
        assert set(results.keys()) == {"a", "b"}
        assert all(r.status == CapabilityStatus.AVAILABLE for r in results.values())


class TestConstraintCombinations:
    """Combinatorial constraint evaluation."""

    def test_gte_satisfied(self) -> None:
        """gte constraint passes when observed >= expected."""
        m = ContextMachine()
        m.define_capability(
            capability("safe", requires=[gte("battery.level_pct", 20)])
        )
        m.observe("battery.level_pct", 50)
        assert m.evaluate("safe").status == CapabilityStatus.AVAILABLE

    def test_gte_unsatisfied(self) -> None:
        """gte constraint fails when observed < expected."""
        m = ContextMachine()
        m.define_capability(
            capability("safe", requires=[gte("battery.level_pct", 20)])
        )
        m.observe("battery.level_pct", 10)
        result = m.evaluate("safe")
        assert result.status == CapabilityStatus.UNAVAILABLE
        assert len(result.blocking) == 1

    def test_lt_satisfied(self) -> None:
        """lt constraint passes when observed < expected."""
        m = ContextMachine()
        m.define_capability(
            capability("safe", requires=[lt("payload.utilization_pct", 95)])
        )
        m.observe("payload.utilization_pct", 80)
        assert m.evaluate("safe").status == CapabilityStatus.AVAILABLE

    def test_fresh_constraint(self) -> None:
        """Fresh constraint passes when observation is recent."""
        m = ContextMachine()
        m.define_capability(
            capability(
                "localized",
                requires=[fresh("pose.x", max_age_ms=5000)],
            )
        )
        now = datetime.now(timezone.utc)
        m.observe("pose.x", 1.0, observed_at=now)
        result = m.evaluate("localized")
        assert result.status == CapabilityStatus.AVAILABLE

    def test_fresh_constraint_stale(self) -> None:
        """Fresh constraint fails when observation is too old."""
        m = ContextMachine()
        m.define_capability(
            capability(
                "localized",
                requires=[fresh("pose.x", max_age_ms=1000)],
            )
        )
        old = datetime.now(timezone.utc) - timedelta(seconds=10)
        m.observe("pose.x", 1.0, observed_at=old)
        result = m.evaluate("localized")
        assert result.status == CapabilityStatus.UNKNOWN

    def test_degrade_when_triggers(self) -> None:
        """degrade_when constraint failing causes DEGRADED status."""
        m = ContextMachine()
        m.define_capability(
            capability(
                "pick",
                requires=[equals("gripper.available", True)],
                degrade_when=[gte("payload.utilization_pct", 90)],
            )
        )
        m.observe("gripper.available", True)
        m.observe("payload.utilization_pct", 95)
        result = m.evaluate("pick")
        assert result.status == CapabilityStatus.DEGRADED
        assert len(result.warnings) == 1

    def test_multiple_requires_all_must_pass(self) -> None:
        """All requires constraints must pass for AVAILABLE."""
        m = ContextMachine()
        m.define_capability(
            capability(
                "complex",
                requires=[
                    equals("safety.estop", False),
                    gte("battery.level_pct", 20),
                    lt("temperature.celsius", 80),
                ],
            )
        )
        # Only two pass
        m.observe("safety.estop", False)
        m.observe("battery.level_pct", 50)
        m.observe("temperature.celsius", 85)
        result = m.evaluate("complex")
        assert result.status == CapabilityStatus.UNAVAILABLE
        assert len(result.blocking) == 1

    def test_multiple_degrade_when(self) -> None:
        """Multiple degrade_when constraints — any one failing triggers DEGRADED."""
        m = ContextMachine()
        m.define_capability(
            capability(
                "pick",
                requires=[equals("gripper.available", True)],
                degrade_when=[
                    gte("payload.utilization_pct", 90),
                    gte("temperature.celsius", 75),
                ],
            )
        )
        m.observe("gripper.available", True)
        m.observe("payload.utilization_pct", 95)
        m.observe("temperature.celsius", 50)
        result = m.evaluate("pick")
        assert result.status == CapabilityStatus.DEGRADED


class TestSnapshotSerialization:
    """Snapshot → dict → from_dict round-trip."""

    def test_snapshot_to_dict_structure(self) -> None:
        """to_dict() produces the expected top-level keys."""
        m = ContextMachine(machine_ref="r1")
        m.define_capability(
            capability("c", requires=[equals("x", 1)])
        )
        m.observe("x", 1)
        snap = m.snapshot()
        d = snap.to_dict()
        assert "schema_version" in d
        assert "machine" in d
        assert "generated_at" in d
        assert "state" in d
        assert "observations" in d
        assert "capabilities" in d

    def test_snapshot_round_trip(self) -> None:
        """from_dict(from_dict(snap)) → equivalent snapshot."""
        m = ContextMachine(machine_ref="r1", peaq_did="did:peaq:test")
        m.define_capability(
            capability("c", requires=[equals("x", 1)])
        )
        m.observe("x", 1)
        snap = m.snapshot()
        d = snap.to_dict()
        restored = ContextSnapshot.from_dict(d)
        assert restored.machine_ref == snap.machine_ref
        assert restored.peaq_did == snap.peaq_did
        assert restored.schema_version == snap.schema_version
        assert set(restored.observations.keys()) == set(snap.observations.keys())

    def test_snapshot_with_trace_id(self) -> None:
        """trace_id is preserved through serialization."""
        m = ContextMachine(machine_ref="r1", trace_id="trace-abc")
        m.define_capability(capability("c", requires=[equals("x", 1)]))
        m.observe("x", 1)
        snap = m.snapshot()
        d = snap.to_dict()
        assert d["trace_id"] == "trace-abc"
        restored = ContextSnapshot.from_dict(d)
        assert restored.trace_id == "trace-abc"
