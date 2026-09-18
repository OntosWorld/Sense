"""Tests for ContextSnapshot redaction API (FR-13)."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sense_ai.errors import InvalidRuleError
from sense_ai.model.observation import TelemetryObservation
from sense_ai.model.result import CapabilityStatus
from sense_ai.model.snapshot import CapabilitySnapshot, ContextSnapshot

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_obs(path: str, value: object) -> TelemetryObservation:
    return TelemetryObservation(
        path=path,
        value=value,
        observed_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )


def make_cap(name: str, status: CapabilityStatus = CapabilityStatus.AVAILABLE) -> CapabilitySnapshot:
    return CapabilitySnapshot(name=name, status=status)


def make_snapshot(
    obs_paths: dict[str, object] | None = None,
    cap_names: list[str] | None = None,
    **overrides,
) -> ContextSnapshot:
    """Minimal snapshot with known, testable content.

    Default content:
      observations: sensor.battery=0.85, sensor.temperature=72.4, actuator.led=True
      capabilities: battery, temperature, led
    """
    obs = {p: make_obs(p, v) for p, v in (obs_paths or {
        "sensor.battery": 0.85,
        "sensor.temperature": 72.4,
        "actuator.led": True,
    }).items()}
    caps = {n: make_cap(n) for n in (cap_names or ["battery", "temperature", "led"])}

    snap = ContextSnapshot(
        machine_ref="test-machine",
        peaq_did="did:peaq:ctx123",
        observations=obs,
        capabilities=caps,
    )
    for k, v in overrides.items():
        setattr(snap, k, v)
    return snap


# ---------------------------------------------------------------------------
# Helper assertions
# ---------------------------------------------------------------------------

def obs_keys(snap: ContextSnapshot) -> set[str]:
    return set(snap.observations.keys())


def cap_keys(snap: ContextSnapshot) -> set[str]:
    return set(snap.capabilities.keys())


# ---------------------------------------------------------------------------
# redact() — observations (allowlist)
# ---------------------------------------------------------------------------

class TestRedactObservationsAllowlist:
    def test_keep_single_path(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["sensor.battery"])
        assert obs_keys(result) == {"sensor.battery"}

    def test_keep_multiple_paths(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["sensor.battery", "actuator.led"])
        assert obs_keys(result) == {"sensor.battery", "actuator.led"}

    def test_keep_all_paths(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["sensor.battery", "sensor.temperature", "actuator.led"])
        assert obs_keys(result) == {"sensor.battery", "sensor.temperature", "actuator.led"}

    def test_keep_no_match_returns_empty(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["nonexistent.path"])
        assert obs_keys(result) == set()

    def test_keep_glob_prefix(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["sensor.*"])
        assert obs_keys(result) == {"sensor.battery", "sensor.temperature"}

    def test_keep_glob_suffix(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["*.battery"])
        assert obs_keys(result) == {"sensor.battery"}

    def test_keep_glob_middle_wildcard(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["sensor.temperature"])
        assert obs_keys(result) == {"sensor.temperature"}


# ---------------------------------------------------------------------------
# redact() — observations (denylist)
# ---------------------------------------------------------------------------

class TestRedactObservationsDenylist:
    def test_drop_single_path(self):
        snap = make_snapshot()
        result = snap.redact(drop_observations=["sensor.temperature"])
        assert obs_keys(result) == {"sensor.battery", "actuator.led"}

    def test_drop_multiple_paths(self):
        snap = make_snapshot()
        result = snap.redact(drop_observations=["sensor.temperature", "actuator.led"])
        assert obs_keys(result) == {"sensor.battery"}

    def test_drop_all_returns_empty(self):
        snap = make_snapshot()
        result = snap.redact(drop_observations=["sensor.battery", "sensor.temperature", "actuator.led"])
        assert obs_keys(result) == set()

    def test_drop_nonexistent_is_noop(self):
        snap = make_snapshot()
        result = snap.redact(drop_observations=["does.not.exist"])
        assert obs_keys(result) == {"sensor.battery", "sensor.temperature", "actuator.led"}

    def test_drop_glob_prefix(self):
        snap = make_snapshot()
        result = snap.redact(drop_observations=["sensor.*"])
        assert obs_keys(result) == {"actuator.led"}


# ---------------------------------------------------------------------------
# redact() — capabilities (allowlist)
# ---------------------------------------------------------------------------

class TestRedactCapabilitiesAllowlist:
    def test_keep_single_capability(self):
        snap = make_snapshot()
        result = snap.redact(keep_capabilities=["battery"])
        assert cap_keys(result) == {"battery"}

    def test_keep_multiple_capabilities(self):
        snap = make_snapshot()
        result = snap.redact(keep_capabilities=["battery", "temperature"])
        assert cap_keys(result) == {"battery", "temperature"}

    def test_keep_glob(self):
        snap = make_snapshot()
        result = snap.redact(keep_capabilities=["b*"])
        assert cap_keys(result) == {"battery"}


# ---------------------------------------------------------------------------
# redact() — capabilities (denylist)
# ---------------------------------------------------------------------------

class TestRedactCapabilitiesDenylist:
    def test_drop_single_capability(self):
        snap = make_snapshot()
        result = snap.redact(drop_capabilities=["temperature"])
        assert cap_keys(result) == {"battery", "led"}

    def test_drop_glob(self):
        snap = make_snapshot()
        result = snap.redact(drop_capabilities=["*"])
        assert cap_keys(result) == set()


# ---------------------------------------------------------------------------
# redact() — combined
# ---------------------------------------------------------------------------

class TestRedactCombined:
    def test_keep_observations_and_capabilities(self):
        snap = make_snapshot()
        result = snap.redact(
            keep_observations=["sensor.battery"],
            keep_capabilities=["battery"],
        )
        assert obs_keys(result) == {"sensor.battery"}
        assert cap_keys(result) == {"battery"}

    def test_mixed_keep_and_drop(self):
        snap = make_snapshot()
        result = snap.redact(
            keep_observations=["sensor.*"],
            drop_capabilities=["led"],
        )
        assert obs_keys(result) == {"sensor.battery", "sensor.temperature"}
        assert cap_keys(result) == {"battery", "temperature"}


# ---------------------------------------------------------------------------
# redact() — mutual-exclusion guard
# ---------------------------------------------------------------------------

class TestRedactMutualExclusion:
    def test_observations_both_keep_and_drop_raises(self):
        snap = make_snapshot()
        with pytest.raises(InvalidRuleError) as exc_info:
            snap.redact(keep_observations=["sensor.battery"], drop_observations=["sensor.battery"])
        assert "keep_observations" in str(exc_info.value) and "drop_observations" in str(exc_info.value)

    def test_capabilities_both_keep_and_drop_raises(self):
        snap = make_snapshot()
        with pytest.raises(InvalidRuleError) as exc_info:
            snap.redact(keep_capabilities=["battery"], drop_capabilities=["battery"])
        assert "keep_capabilities" in str(exc_info.value) and "drop_capabilities" in str(exc_info.value)

    def test_both_domains_conflict_in_same_call(self):
        snap = make_snapshot()
        with pytest.raises(InvalidRuleError):
            snap.redact(
                keep_observations=["sensor.battery"],
                drop_observations=["sensor.battery"],
                keep_capabilities=["battery"],
                drop_capabilities=["battery"],
            )


# ---------------------------------------------------------------------------
# redact() — immutability
# ---------------------------------------------------------------------------

class TestRedactIdempotence:
    def test_original_unchanged(self):
        snap = make_snapshot()
        snap.redact(keep_observations=["sensor.battery"])
        assert obs_keys(snap) == {"sensor.battery", "sensor.temperature", "actuator.led"}

    def test_result_is_new_instance(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["sensor.battery"])
        assert result is not snap

    def test_peaq_did_preserved(self):
        snap = make_snapshot()
        result = snap.redact(keep_observations=["sensor.battery"])
        assert result.peaq_did == snap.peaq_did


# ---------------------------------------------------------------------------
# local_view()
# ---------------------------------------------------------------------------

class TestLocalView:
    def test_strips_peaq_did(self):
        snap = make_snapshot()
        assert snap.peaq_did == "did:peaq:ctx123"
        result = snap.local_view()
        assert result.peaq_did is None

    def test_no_default_denylist(self):
        # local_view() only strips peaq_did; no hardcoded default filters
        snap = make_snapshot()
        result = snap.local_view()
        assert obs_keys(result) == {"sensor.battery", "sensor.temperature", "actuator.led"}
        assert cap_keys(result) == {"battery", "temperature", "led"}

    def test_additional_drop_observations(self):
        snap = make_snapshot()
        result = snap.local_view(drop_observations=["sensor.temperature"])
        assert obs_keys(result) == {"sensor.battery", "actuator.led"}

    def test_additional_drop_capabilities(self):
        snap = make_snapshot()
        result = snap.local_view(drop_capabilities=["temperature"])
        assert cap_keys(result) == {"battery", "led"}

    def test_returns_new_instance(self):
        snap = make_snapshot()
        result = snap.local_view()
        assert result is not snap

    def test_machine_ref_preserved(self):
        snap = make_snapshot()
        result = snap.local_view()
        assert result.machine_ref == snap.machine_ref


# ---------------------------------------------------------------------------
# publishable_view()
# ---------------------------------------------------------------------------

class TestPublishableView:
    def test_strips_peaq_did(self):
        snap = make_snapshot()
        assert snap.peaq_did == "did:peaq:ctx123"
        result = snap.publishable_view()
        assert result.peaq_did is None

    def test_default_view_excludes_raw_observations(self):
        snap = make_snapshot()
        result = snap.publishable_view()
        assert obs_keys(result) == set()
        assert cap_keys(result) == {"battery", "temperature", "led"}

    def test_additional_keep_observations(self):
        snap = make_snapshot()
        result = snap.publishable_view(keep_observations=["sensor.*"])
        assert obs_keys(result) == {"sensor.battery", "sensor.temperature"}

    def test_additional_keep_capabilities(self):
        snap = make_snapshot()
        result = snap.publishable_view(keep_capabilities=["battery", "temperature"])
        assert cap_keys(result) == {"battery", "temperature"}

    def test_returns_new_instance(self):
        snap = make_snapshot()
        result = snap.publishable_view()
        assert result is not snap

    def test_machine_ref_preserved(self):
        snap = make_snapshot()
        result = snap.publishable_view()
        assert result.machine_ref == snap.machine_ref


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestRedactEdgeCases:
    def test_empty_observations_and_capabilities(self):
        # Pass explicit empty dicts to bypass the "default content" fallback
        snap = ContextSnapshot(
            machine_ref="test-machine",
            peaq_did="did:peaq:ctx123",
            observations={},
            capabilities={},
        )
        result = snap.redact(keep_observations=["sensor.*"])
        assert obs_keys(result) == set()
        assert cap_keys(result) == set()

    def test_drop_glob_matches_nothing(self):
        snap = make_snapshot()
        result = snap.redact(drop_observations=["nomatch.*"])
        assert obs_keys(result) == {"sensor.battery", "sensor.temperature", "actuator.led"}

    def test_local_view_then_redact_composes(self):
        """Result of local_view() can be further redacted."""
        snap = make_snapshot()
        local = snap.local_view()
        further = local.redact(keep_observations=["sensor.battery"])
        assert obs_keys(further) == {"sensor.battery"}

    def test_publishable_view_then_redact_composes(self):
        snap = make_snapshot()
        pub = snap.publishable_view()
        further = pub.redact(drop_observations=["sensor.temperature"])
        assert obs_keys(further) == set()

    def test_no_peaq_did_local_view_still_works(self):
        snap = make_snapshot()
        snap.peaq_did = None
        result = snap.local_view()
        assert result.peaq_did is None

    def test_no_peaq_did_publishable_view_still_works(self):
        snap = make_snapshot()
        snap.peaq_did = None
        result = snap.publishable_view()
        assert result.peaq_did is None

    def test_trace_id_preserved_through_redact(self):
        snap = make_snapshot(trace_id="trace-abc123")
        result = snap.redact(keep_observations=["sensor.battery"])
        assert result.trace_id == "trace-abc123"
