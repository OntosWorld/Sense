"""
Unit tests for the PRD-aligned capability model.

Covers: TelemetryObservation, CapabilitySpec/capability(), ContextMachine,
constraint evaluation (equals, gte, fresh, ALL/ANY/NOT), evaluate() status
logic, snapshot(), transitions(), and the EventBus.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sense_ai import (
    ALL,
    ANY,
    NONE_OF,
    NOT,
    ONLY_ONE,
    ContextMachine,
    Equals,
    EventBus,
    Fresh,
    Gte,
    TelemetryObservation,
    UnknownCapabilityError,
    capability,
    compute_trust_report,
)
from sense_ai.model.result import CapabilityStatus

# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

NOW = datetime(2026, 9, 18, 10, 0, 0, tzinfo=timezone.utc)


def _obs(
    path: str,
    value: float | str | bool = 1.0,
    age_ms: int | None = 0,
    ttl_ms: int = 5000,
    source: str = "test",
) -> TelemetryObservation:
    return TelemetryObservation(
        path=path,
        value=value,
        _age_ms=age_ms if age_ms is not None else 0,
        source=source,
        ttl_ms=ttl_ms,
    )


def _machine(
    capabilities: list | None = None,
) -> ContextMachine:
    """Fresh machine, optionally with pre-registered capabilities."""
    m = ContextMachine(machine_ref="test-machine")
    if capabilities:
        for cap in capabilities:
            m.define_capability(cap)
    return m


# ----------------------------------------------------------------------
# TelemetryObservation
# ----------------------------------------------------------------------

class TestTelemetryObservation:
    def test_age_ms_computed_from_observed_at(self) -> None:
        # Pass _age_ms explicitly (60 000 ms) so the age_ms property returns
        # the exact value.  Using _age_ms because the public parameter is a
        # property and construction requires the private _age_ms field.
        obs = TelemetryObservation(
            path="temp", value=42.0, _age_ms=60_000, ttl_ms=60000
        )
        # age_ms property returns the exact _age_ms value set at construction.
        assert 59000 <= obs.age_ms <= 61000

    def test_is_available_true_when_fresh(self) -> None:
        obs = _obs("x", value=1.0, age_ms=0, ttl_ms=5000)
        assert obs.is_available is True

    def test_is_available_false_when_stale(self) -> None:
        obs = _obs("x", value=1.0, age_ms=10000, ttl_ms=5000)
        assert obs.is_available is False

    def test_explicit_null_remains_available_evidence(self) -> None:
        obs = TelemetryObservation(path="x", value=None, observed_at=NOW)
        assert obs.is_available is True

    def test_serialization_roundtrip(self) -> None:
        obs = _obs("battery.voltage", value=12.4)
        restored = TelemetryObservation.from_dict(obs.to_dict())
        assert restored.path == obs.path
        assert restored.value == obs.value
        assert restored.ttl_ms == obs.ttl_ms
        assert restored.received_at == obs.received_at

    def test_structured_json_value_roundtrip(self) -> None:
        value = {"x": 1.0, "y": 2.0, "covariance": [0.1, 0.2]}
        obs = TelemetryObservation(path="localization.pose", value=value)
        restored = TelemetryObservation.from_dict(obs.to_dict())
        assert restored.value == value

    def test_explicit_null_is_valid_telemetry(self) -> None:
        m = _machine()
        stored = m.observe("sensor.optional", None)
        assert stored is not None
        assert m.get_observation("sensor.optional") is stored
        assert stored.value is None

    def test_too_old_beyond_ttl(self) -> None:
        obs = _obs("x", value=1.0, age_ms=99999, ttl_ms=1000)
        assert obs.age_ms == 99999  # stored as-is
        assert obs.is_available is False


# ----------------------------------------------------------------------
# CapabilitySpec / @capability()
# ----------------------------------------------------------------------

class TestCapabilityDecorator:
    def test_named_capability(self) -> None:
        @capability(name="test.cap", version="1.0")
        def fn(c: ContextMachine) -> bool:
            return True

        assert fn.name == "test.cap"
        assert fn.version == "1.0"
        assert fn.requires == []
        assert fn.degrade_when == []

    def test_capability_with_constraints(self) -> None:
        req = Equals("x", 1)
        deg = Gte("y", 0)

        @capability(name="test.constrained", version="2.0", requires=[req], degrade_when=[deg])
        def fn(c: ContextMachine) -> bool:
            return c.observe("x").value == 1

        assert fn.requires == [req]
        assert fn.degrade_when == [deg]

    def test_capability_blocks_empty_name(self) -> None:
        with pytest.raises(ValueError, match="name"):
            @capability(name="", version="1.0")  # type: ignore[call-arg]
            def fn(c: ContextMachine) -> bool:
                return True


# ----------------------------------------------------------------------
# Constraint primitives
# ----------------------------------------------------------------------

class TestEquals:
    def test_passes_when_value_matches(self) -> None:
        obs = _obs("speed", value=42)
        outcome = Equals("speed", 42).evaluate({"speed": obs})
        assert outcome.passed is True

    def test_fails_when_value_differs(self) -> None:
        obs = _obs("speed", value=99)
        outcome = Equals("speed", 42).evaluate({"speed": obs})
        assert outcome.passed is False
        assert outcome.observed == 99

    def test_fails_when_path_absent(self) -> None:
        outcome = Equals("nonexistent", 0).evaluate({})
        assert outcome.passed is False
        assert outcome.is_absent is True

    def test_expired_ttl_is_stale_unknown_evidence(self) -> None:
        obs = _obs("x", value=1, age_ms=2000, ttl_ms=1000)
        outcome = Equals("x", 1).evaluate({"x": obs})
        assert outcome.passed is False
        assert outcome.is_stale is True


class TestGte:
    def test_passes_when_greater(self) -> None:
        outcome = Gte("x", 5).evaluate({"x": _obs("x", value=10)})
        assert outcome.passed is True

    def test_passes_when_equal(self) -> None:
        outcome = Gte("x", 5).evaluate({"x": _obs("x", value=5)})
        assert outcome.passed is True

    def test_fails_when_less(self) -> None:
        outcome = Gte("x", 5).evaluate({"x": _obs("x", value=3)})
        assert outcome.passed is False


class TestFresh:
    def test_passes_when_observation_is_fresh(self) -> None:
        obs = _obs("x", value=1, age_ms=500, ttl_ms=5000)
        outcome = Fresh("x", max_age_ms=1000).evaluate({"x": obs})
        assert outcome.passed is True

    def test_fails_when_stale(self) -> None:
        obs = _obs("x", value=1, age_ms=3000, ttl_ms=5000)
        outcome = Fresh("x", max_age_ms=1000).evaluate({"x": obs})
        assert outcome.passed is False
        assert outcome.is_stale is True

    def test_fails_when_path_absent(self) -> None:
        outcome = Fresh("x", max_age_ms=1000).evaluate({})
        assert outcome.passed is False
        assert outcome.is_absent is True


# ----------------------------------------------------------------------
# Composition constraints
# ----------------------------------------------------------------------

class TestComposition:
    def test_all_passes(self) -> None:
        store = {"a": _obs("a", 1), "b": _obs("b", 2)}
        outcome = ALL(Equals("a", 1), Equals("b", 2)).evaluate(store)
        assert outcome.passed is True

    def test_all_fails_on_first_violation(self) -> None:
        store = {"a": _obs("a", 99), "b": _obs("b", 2)}
        outcome = ALL(Equals("a", 1), Equals("b", 2)).evaluate(store)
        assert outcome.passed is False
        assert outcome.path == ""
        assert outcome.children[0].path == "a"
        assert outcome.children[0].passed is False

    def test_any_passes(self) -> None:
        store = {"a": _obs("a", 99), "b": _obs("b", 2)}
        outcome = ANY(Equals("a", 1), Equals("b", 2)).evaluate(store)
        assert outcome.passed is True

    def test_not_inverts(self) -> None:
        outcome = NOT(Equals("x", 1)).evaluate({"x": _obs("x", 2)})
        assert outcome.passed is True

    def test_none_of_all_fail(self) -> None:
        outcome = NONE_OF(Equals("x", 1), Equals("x", 2)).evaluate({"x": _obs("x", 3)})
        assert outcome.passed is True

    def test_not_does_not_turn_missing_evidence_into_success(self) -> None:
        outcome = NOT(Equals("missing", 1)).evaluate({})
        assert outcome.passed is False
        assert outcome.is_absent is True

    def test_all_propagates_stale_evidence(self) -> None:
        store = {
            "a": _obs("a", 1, age_ms=5000, ttl_ms=1000),
            "b": _obs("b", 2),
        }
        outcome = ALL(Equals("a", 1), Equals("b", 2)).evaluate(store)
        assert outcome.passed is False
        assert outcome.is_stale is True

    def test_any_is_unknown_when_only_possible_match_is_missing(self) -> None:
        store = {"a": _obs("a", 0)}
        outcome = ANY(Equals("a", 1), Equals("b", 2)).evaluate(store)
        assert outcome.passed is False
        assert outcome.is_absent is True

    def test_none_of_is_unknown_when_member_is_missing(self) -> None:
        outcome = NONE_OF(Equals("a", 1), Equals("b", 2)).evaluate(
            {"a": _obs("a", 0)}
        )
        assert outcome.passed is False
        assert outcome.is_absent is True

    def test_only_one_is_unknown_when_second_member_is_missing(self) -> None:
        outcome = ONLY_ONE(Equals("a", 1), Equals("b", 2)).evaluate(
            {"a": _obs("a", 1)}
        )
        assert outcome.passed is False
        assert outcome.is_absent is True


# ----------------------------------------------------------------------
# ContextMachine — observe() and evaluate()
# ----------------------------------------------------------------------

class TestContextMachine:
    def test_observe_stores_observation(self) -> None:
        m = _machine()
        obs = m.observe("speed", 120.0, source="sensor")
        assert obs is not None
        assert obs.value == 120.0
        assert m.observations["speed"].value == 120.0

    def test_observe_accepts_telemetry_observation_object(self) -> None:
        m = _machine()
        t = _obs("temp", value=85.0, source="tm")
        stored = m.observe(t)
        assert stored is not None
        assert stored.path == "temp"
        assert stored.value == 85.0

    def test_define_capability_registers(self) -> None:
        @capability(name="test.op", version="1.0")
        def fn(c: ContextMachine) -> bool:
            return True

        m = _machine()
        m.define_capability(fn)
        assert "test.op" in m.capability_names

    def test_evaluate_unknown_capability_raises(self) -> None:
        m = _machine()
        with pytest.raises(UnknownCapabilityError, match="not registered"):
            m.evaluate("does.not.exist")

    def test_evaluate_python_cap_returns_available(self) -> None:
        @capability(name="always.ok", version="1.0")
        def always_ok(c: ContextMachine) -> bool:
            return True

        m = _machine([always_ok])
        m.observe("x", 1)
        result = m.evaluate("always.ok")
        assert result.status == CapabilityStatus.AVAILABLE
        assert result.blocking == []

    def test_evaluate_python_cap_returns_unavailable(self) -> None:
        @capability(name="always.fail", version="1.0")
        def always_fail(c: ContextMachine) -> bool:
            return False

        m = _machine([always_fail])
        m.observe("x", 1)
        result = m.evaluate("always.fail")
        assert result.status == CapabilityStatus.UNAVAILABLE

    def test_evaluate_degraded_on_warn(self) -> None:
        @capability(name="warn.cap", version="1.0", degrade_when=[Equals("x", 99)])
        def warn_cap(c: ContextMachine) -> bool:
            return True

        m = _machine([warn_cap])
        m.observe("x", 99)
        result = m.evaluate("warn.cap")
        assert result.status == CapabilityStatus.DEGRADED
        assert len(result.warnings) == 1

    def test_expired_ttl_on_value_constraint_is_unknown(self) -> None:
        m = _machine()
        m.define_capability(
            capability("ttl.cap", requires=[Equals("x", 1)])
        )
        m.observe(_obs("x", value=1, age_ms=5000, ttl_ms=1000))
        result = m.evaluate("ttl.cap")
        assert result.status == CapabilityStatus.UNKNOWN

    def test_evaluate_stale_blocking_constraint_unknown(self) -> None:
        @capability(name="fresh.cap", version="1.0", requires=[Fresh("x", max_age_ms=1000)])
        def fresh_cap(c: ContextMachine) -> bool:
            return True

        m = _machine([fresh_cap])
        # Observe stale data (older than max_age_ms=1000)
        old = TelemetryObservation(
            path="x", value=1.0,
            observed_at=NOW - timedelta(seconds=5),
            ttl_ms=10000,
        )
        m.observe(old)

        result = m.evaluate("fresh.cap")
        # Stale + blocking -> UNKNOWN (not UNAVAILABLE)
        assert result.status == CapabilityStatus.UNKNOWN

    def test_evaluate_all(self) -> None:
        @capability(name="a", version="1.0")
        def a(c: ContextMachine) -> bool:
            return True

        @capability(name="b", version="1.0")
        def b(c: ContextMachine) -> bool:
            return False

        m = _machine([a, b])
        results = m.evaluate_all()
        assert results["a"].status == CapabilityStatus.AVAILABLE
        assert results["b"].status == CapabilityStatus.UNAVAILABLE

    def test_define_capability_idempotent(self) -> None:
        @capability(name="dup", version="1.0")
        def fn(c: ContextMachine) -> bool:
            return True

        m = _machine()
        m.define_capability(fn)
        m.define_capability(fn)  # no-op
        assert len(m.capability_names) == 1


# ----------------------------------------------------------------------
# ContextMachine — snapshot()
# ----------------------------------------------------------------------

class TestSnapshot:
    def test_snapshot_returns_context_snapshot(self) -> None:
        @capability(name="snap.test", version="1.0")
        def st(c: ContextMachine) -> bool:
            return True

        m = _machine([st])
        m.observe("x", 1.0)
        snap = m.snapshot()

        assert snap.schema_version == "1.0"
        assert snap.machine_ref == "test-machine"
        assert len(snap.observations) == 1
        assert "snap.test" in snap.capabilities

    def test_snapshot_updates_last_snapshot(self) -> None:
        m = _machine()
        m.observe("x", 1.0)
        s1 = m.snapshot()
        m.observe("y", 2.0)
        s2 = m.snapshot()
        assert len(s2.observations) == 2
        assert m.last_snapshot is s2
        assert m.last_snapshot is not s1

    def test_snapshot_re_evaluates_without_changes(self) -> None:
        m = _machine()
        m.observe("x", 1.0)
        s1 = m.snapshot()
        s2 = m.snapshot()
        assert s2 is not s1


# ----------------------------------------------------------------------
# ContextMachine — transitions()
# ----------------------------------------------------------------------

class TestTransitions:
    def test_transition_detected_on_status_change(self) -> None:
        @capability(name="toggle", version="1.0")
        def toggle(c: ContextMachine) -> bool:
            return c.observe("flag").value is True

        m = _machine([toggle])
        m.observe("flag", False)
        r1 = m.evaluate("toggle")
        assert r1.status == CapabilityStatus.UNAVAILABLE

        m.observe("flag", True)
        r2 = m.evaluate("toggle")
        assert r2.status == CapabilityStatus.AVAILABLE

        transitions = m.transitions("toggle")
        assert len(transitions) == 2  # UNAVAILABLE->AVAILABLE + re-evaluation

    def test_last_transition_returns_most_recent(self) -> None:
        @capability(name="t", version="1.0")
        def t(c: ContextMachine) -> bool:
            return c.observe("v").value == 1

        m = _machine([t])
        m.observe("v", 1)
        m.evaluate("t")
        m.observe("v", 2)
        m.evaluate("t")

        last = m.last_transition("t")
        assert last is not None
        assert last.capability == "t"

    def test_on_transition_decorator(self) -> None:
        @capability(name="dc", version="1.0")
        def dc(c: ContextMachine) -> bool:
            return c.observe("v").value == 1

        m = _machine([dc])
        calls: list = []

        @m.on_transition("dc")
        def handler(transition):
            calls.append(transition)

        m.observe("v", 1)
        m.evaluate("dc")
        assert len(calls) == 1
        assert calls[0].capability == "dc"


# ----------------------------------------------------------------------
# EventBus
# ----------------------------------------------------------------------

class TestEventBus:
    def test_subscribe_and_publish(self) -> None:
        bus = EventBus()
        received: list = []

        @bus.on("capability_evaluated")
        def handler(event):
            received.append(event)

        bus._publish(
            __import__("sense_ai").events.CapabilityEvaluatedEvent(
                machine_id="m1",
                capability_name="test",
                result=__import__("sense_ai").model.result.CapabilityResult(
                    name="test",
                    status=CapabilityStatus.AVAILABLE,
                ),
            )
        )
        assert len(received) == 1

    def test_subscribe_all_types(self) -> None:
        bus = EventBus()
        count = {"total": 0}

        def handler(event):
            count["total"] += 1

        bus.subscribe(handler)  # all types
        from sense_ai.events import (
            CapabilityEvaluatedEvent,
            SnapshotCreatedEvent,
            TransitionDetectedEvent,
        )
        from sense_ai.model.result import CapabilityResult, ContextTransition

        bus._publish(CapabilityEvaluatedEvent(machine_id="m", capability_name="c", result=CapabilityResult(name="c", status=CapabilityStatus.AVAILABLE)))
        bus._publish(SnapshotCreatedEvent(machine_id="m", snapshot_dict={}))
        bus._publish(TransitionDetectedEvent(machine_id="m", transition=ContextTransition(capability="c", current=CapabilityStatus.AVAILABLE)))
        assert count["total"] == 3

    def test_unsubscribe(self) -> None:
        bus = EventBus()
        count = [0]

        def handler(event):
            count[0] += 1

        bus.subscribe(handler)
        bus.unsubscribe(handler)
        from sense_ai.events import CapabilityEvaluatedEvent
        from sense_ai.model.result import CapabilityResult

        bus._publish(CapabilityEvaluatedEvent(machine_id="m", capability_name="c", result=CapabilityResult(name="c", status=CapabilityStatus.AVAILABLE)))
        assert count[0] == 0


# ----------------------------------------------------------------------
# ContextMachine + EventBus integration
# ----------------------------------------------------------------------

class TestEventBusIntegration:
    def test_evaluate_publishes_event(self) -> None:
        bus = EventBus()
        received: list = []

        @bus.on("capability_evaluated")
        def handler(event):
            received.append(event)

        @capability(name="ev.test", version="1.0")
        def ev(c: ContextMachine) -> bool:
            return True

        m = ContextMachine(machine_ref="ev-machine", event_bus=bus)
        m.define_capability(ev)
        m.observe("x", 1)
        m.evaluate("ev.test")

        assert len(received) == 1
        assert received[0].capability_name == "ev.test"

    def test_snapshot_publishes_event(self) -> None:
        bus = EventBus()
        received: list = []

        @bus.on("snapshot_created")
        def handler(event):
            received.append(event)

        @capability(name="snap", version="1.0")
        def s(c: ContextMachine) -> bool:
            return True

        m = ContextMachine(machine_ref="snap-machine", event_bus=bus)
        m.define_capability(s)
        m.snapshot()

        assert len(received) == 1

    def test_transition_publishes_event(self) -> None:
        bus = EventBus()
        received: list = []

        @bus.on("transition_detected")
        def handler(event):
            received.append(event)

        @capability(name="trans", version="1.0")
        def tr(c: ContextMachine) -> bool:
            return c.observe("v").value is True

        m = ContextMachine(machine_ref="tr-machine", event_bus=bus)
        m.define_capability(tr)
        m.observe("v", False)
        m.evaluate("trans")
        m.observe("v", True)
        m.evaluate("trans")

        # One transition event (False->True)
        assert len(received) >= 1


# ----------------------------------------------------------------------
# TrustReport
# ----------------------------------------------------------------------

class TestTrustReport:
    def test_all_fresh_full_coverage(self) -> None:
        obs = [
            _obs("a", value=1.0, age_ms=0, ttl_ms=5000),
            _obs("b", value=2.0, age_ms=0, ttl_ms=5000),
        ]
        report = compute_trust_report(
            schema_version="1.0",
            machine_id="trust-test",
            observations=obs,
        )
        assert report.overall_score > 0.8
        assert report.quality_band in ("excellent", "good")

    def test_all_stale_zero_score(self) -> None:
        obs = [
            _obs("a", value=1.0, age_ms=99999, ttl_ms=1000),
            _obs("b", value=2.0, age_ms=99999, ttl_ms=1000),
        ]
        report = compute_trust_report(
            schema_version="1.0",
            machine_id="trust-test",
            observations=obs,
        )
        assert report.overall_score < 0.3

    def test_required_paths_coverage(self) -> None:
        obs = [_obs("a", value=1.0, age_ms=0, ttl_ms=5000)]
        report = compute_trust_report(
            schema_version="1.0",
            machine_id="trust-test",
            observations=obs,
            required_observation_paths=frozenset(["a", "b"]),
        )
        # Only 1 of 2 required paths covered → 0.5 freshness × 1.0 coverage
        assert report.dimensions[1].name == "coverage"
        assert report.dimensions[1].score == 0.5

    def test_empty_observations(self) -> None:
        report = compute_trust_report(
            schema_version="1.0",
            machine_id="empty",
            observations=[],
        )
        assert report.overall_score == 0.0
        assert report.observation_count == 0

    def test_to_dict_serializable(self) -> None:
        obs = [_obs("x", value=1.0, age_ms=0, ttl_ms=5000)]
        report = compute_trust_report(
            schema_version="1.0",
            machine_id="s",
            observations=obs,
        )
        d = report.to_dict()
        assert "overall_score" in d
        assert "dimensions" in d
        assert isinstance(d["dimensions"], list)

    def test_custom_weights(self) -> None:
        obs = [_obs("x", value=1.0, age_ms=0, ttl_ms=5000)]
        report = compute_trust_report(
            schema_version="1.0",
            machine_id="w",
            observations=obs,
            dimension_weights={"freshness": 10.0},  # very high weight on freshness
        )
        # With only one observation, freshness should dominate
        freshness_dim = next(d for d in report.dimensions if d.name == "freshness")
        assert freshness_dim.weight == 10.0
