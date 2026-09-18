"""Contract tests: JSON Schema validation round-trips.

Tests that snapshots produced by the SDK pass schema validation,
and that known-bad payloads are rejected with the correct error types.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sense_ai.errors import SchemaValidationError, SerializationError
from sense_ai.model.observation import TelemetryObservation
from sense_ai.model.result import CapabilityStatus
from sense_ai.model.snapshot import CapabilitySnapshot, ContextSnapshot

try:
    from sense_ai.serialization import validate_draft202012
except ImportError:
    validate_draft202012 = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA_PATH = Path(__file__).parents[2] / "schemas" / "context-1.0.schema.json"


def _full_snapshot() -> ContextSnapshot:
    """A snapshot with all optional fields populated."""
    return ContextSnapshot(
        schema_version="1.0",
        machine_ref="machine-001",
        peaq_did="did:peaq:machine-001",
        generated_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        observations={
            "battery.level_pct": TelemetryObservation(
                path="battery.level_pct",
                value=85,
                observed_at=datetime(2024, 1, 15, 11, 59, 0, tzinfo=timezone.utc),
                source="battery_controller",
                ttl_ms=5000,
            ),
        },
        capabilities={
            "test.capability": CapabilitySnapshot(
                name="test.capability",
                status=CapabilityStatus.AVAILABLE,
                blocking=[],
                warnings=[
                    {
                        "code": "PAYLOAD_OK",
                        "severity": "warning",
                        "path": "payload.weight_kg",
                        "expected": "<= 50kg",
                        "observed": 23.5,
                    }
                ],
            ),
        },
        trace_id="trace-abc123",
    )


# ---------------------------------------------------------------------------
# Schema validation: valid snapshots
# ---------------------------------------------------------------------------

@pytest.mark.skipif(validate_draft202012 is None, reason="jsonschema not installed")
class TestSchemaValidationValid:
    def test_minimal_valid_snapshot_passes(self) -> None:
        snap = ContextSnapshot(
            schema_version="1.0",
            machine_ref="machine-001",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observations={},
            capabilities={},
        )
        errors = validate_draft202012(snap.to_dict(), SCHEMA_PATH)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_full_snapshot_passes(self) -> None:
        snap = _full_snapshot()
        errors = validate_draft202012(snap.to_dict(), SCHEMA_PATH)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_observations_with_all_optional_fields_passes(self) -> None:
        snap = ContextSnapshot(
            schema_version="1.0",
            machine_ref="machine-001",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observations={
                "battery.level_pct": TelemetryObservation(
                    path="battery.level_pct",
                    value=100,
                    observed_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
                    source="battery_controller",
                    ttl_ms=5000,
                ),
            },
            capabilities={
                "test.cap": CapabilitySnapshot(
                    name="test.cap",
                    status=CapabilityStatus.AVAILABLE,
                    blocking=[],
                    warnings=[
                        {
                            "code": "PAYLOAD_OK",
                            "severity": "warning",
                            "path": "payload.weight_kg",
                            "expected": "<= 50kg",
                            "observed": 23.5,
                        }
                    ],
                ),
            },
            trace_id="trace-abc123",
        )
        errors = validate_draft202012(snap.to_dict(), SCHEMA_PATH)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_machine_ref_null_fields_passes(self) -> None:
        snap = ContextSnapshot(
            schema_version="1.0",
            machine_ref=None,
            peaq_did=None,
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observations={},
            capabilities={},
        )
        errors = validate_draft202012(snap.to_dict(), SCHEMA_PATH)
        assert errors == [], f"Expected no errors, got: {errors}"

    def test_machine_ref_with_peaq_did_passes(self) -> None:
        snap = ContextSnapshot(
            schema_version="1.0",
            machine_ref="machine-001",
            peaq_did="did:peaq:machine-001",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observations={},
            capabilities={},
        )
        errors = validate_draft202012(snap.to_dict(), SCHEMA_PATH)
        assert errors == [], f"Expected no errors, got: {errors}"


# ---------------------------------------------------------------------------
# Schema validation: invalid payloads
# ---------------------------------------------------------------------------

@pytest.mark.skipif(validate_draft202012 is None, reason="jsonschema not installed")
class TestSchemaValidationErrors:
    def test_missing_required_schema_version(self) -> None:
        payload: dict = {
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [],
            "capabilities": {},
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0
        assert any(
            "schema_version" in e.json_path or "required" in e.message.lower()
            for e in errors
        )

    def test_wrong_schema_version_const(self) -> None:
        payload: dict = {
            "schema_version": "99.0",  # must be "1.0"
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [],
            "capabilities": {},
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0

    def test_invalid_capability_status(self) -> None:
        payload: dict = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [],
            "capabilities": {
                "test.cap": {
                    "status": "INVALID_STATUS",
                    "reasons": [],
                }
            },
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0
        assert any("AVAILABLE" in str(e.message) or "enum" in str(e.message).lower()
                   for e in errors)

    def test_invalid_reason_severity(self) -> None:
        payload: dict = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [],
            "capabilities": {
                "test.cap": {
                    "status": "AVAILABLE",
                    "reasons": [
                        {
                            "code": "TEST_CODE",
                            "severity": "invalid_severity",
                        }
                    ],
                }
            },
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0

    def test_observation_invalid_path_format(self) -> None:
        payload: dict = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [
                {
                    "path": "invalid-path!",  # must match pattern
                    "value": 42,
                    "observed_at": "2024-01-01T00:00:00Z",
                }
            ],
            "capabilities": {},
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0

    def test_observation_missing_required_field(self) -> None:
        payload: dict = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [
                {
                    "path": "battery.level_pct",
                    "value": 42,
                    # missing "observed_at"
                }
            ],
            "capabilities": {},
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0

    def test_additional_properties_rejected(self) -> None:
        payload: dict = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [],
            "capabilities": {},
            "unknown_field": "should not be here",
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# SchemaValidationError attributes
# ---------------------------------------------------------------------------

@pytest.mark.skipif(validate_draft202012 is None, reason="jsonschema not installed")
class TestSchemaValidationError:
    def test_error_carries_json_path(self) -> None:
        payload = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [
                {"path": "bad!", "value": 1, "observed_at": "2024-01-01T00:00:00Z"}
            ],
            "capabilities": {},
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0
        err = errors[0]
        assert isinstance(err, SchemaValidationError)
        assert err.json_path is not None
        assert err.message is not None
        assert err.schema_version is not None

    def test_errors_collect_all_failures(self) -> None:
        # Multiple independent failures should all be reported
        payload: dict = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [
                {"path": "bad!", "value": 1, "observed_at": "2024-01-01T00:00:00Z"},
                {"path": "also-bad!", "value": 2, "observed_at": "2024-01-01T00:00:00Z"},
            ],
            "capabilities": {
                "bad_cap": {"status": "NOT_VALID"},
            },
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        # Should collect at least 3 errors (2 paths + 1 status)
        assert len(errors) >= 3


# ---------------------------------------------------------------------------
# SerializationError on malformed schema
# ---------------------------------------------------------------------------

class TestSerializationError:
    def test_nonexistent_schema_file_raises(self) -> None:
        if validate_draft202012 is None:
            pytest.skip("jsonschema not installed")
        with pytest.raises(SerializationError):
            validate_draft202012({}, Path("/nonexistent/path/schema.json"))

    def test_schema_validation_error_is_schema_version_aware(self) -> None:
        if validate_draft202012 is None:
            pytest.skip("jsonschema not installed")
        payload = {
            "schema_version": "1.0",
            "generated_at": "2024-01-01T00:00:00Z",
            "observations": [],
            "capabilities": {"bad": {"status": "INVALID"}},
        }
        errors = validate_draft202012(payload, SCHEMA_PATH)
        assert len(errors) > 0
        # Schema version should be extractable from the schema
        assert errors[0].schema_version is not None
