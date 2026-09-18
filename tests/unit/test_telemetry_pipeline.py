"""Telemetry validation, normalization and UNKNOWN semantics."""

from __future__ import annotations

from sense_ai import (
    ALL,
    ANY,
    CapabilityStatus,
    ContextMachine,
    SenseConfig,
    TelemetryFieldSpec,
    TelemetryMapping,
    TelemetryNormalizer,
    TelemetrySchema,
    capability,
    equals,
    gte,
)


def test_normalizer_converts_raw_ratio_to_percent() -> None:
    schema = TelemetrySchema()
    schema.define(
        TelemetryFieldSpec(
            path="battery.level_pct",
            kind="number",
            minimum=0,
            maximum=100,
            ttl_ms=5000,
        )
    )
    normalizer = TelemetryNormalizer.from_dict(
        {
            "mappings": [
                {
                    "source": "battery.ratio",
                    "target": "battery.level_pct",
                    "transform": "ratio_to_percent",
                }
            ]
        },
        schema=schema,
    )

    result = normalizer.normalize({"battery": {"ratio": 0.72}})

    assert result.ok
    assert result.observations[0].value == 72.0
    assert result.observations[0].ttl_ms == 5000
    assert result.observations[0].is_valid


def test_transform_failure_is_preserved_as_invalid_evidence() -> None:
    normalizer = TelemetryNormalizer(
        [
            TelemetryMapping.from_dict(
                {
                    "source": "battery",
                    "target": "battery.level_pct",
                    "transform": "ratio_to_percent",
                }
            )
        ]
    )

    result = normalizer.normalize({"battery": "not-a-number"})

    assert not result.ok
    assert len(result.observations) == 1
    assert not result.observations[0].is_valid
    assert result.observations[0].validation_errors


def test_schema_invalid_value_makes_capability_unknown() -> None:
    schema = TelemetrySchema()
    schema.define(TelemetryFieldSpec(path="battery.level_pct", kind="number"))
    machine = ContextMachine(telemetry_schema=schema)
    machine.define_capability(
        capability("power.ready", requires=[gte("battery.level_pct", 20)])
    )

    machine.observe("battery.level_pct", "high")
    result = machine.evaluate("power.ready")

    assert result.status == CapabilityStatus.UNKNOWN
    assert result.unknown_paths == ["battery.level_pct"]
    assert result.blocking[0].is_invalid


def test_numeric_rule_type_error_is_unknown_without_explicit_schema() -> None:
    machine = ContextMachine()
    machine.define_capability(
        capability("power.ready", requires=[gte("battery.level_pct", 20)])
    )
    machine.observe("battery.level_pct", "high")

    result = machine.evaluate("power.ready")

    assert result.status == CapabilityStatus.UNKNOWN
    assert result.blocking[0].is_invalid


def test_composed_rule_preserves_exact_unknown_leaf_path() -> None:
    machine = ContextMachine()
    machine.define_capability(
        capability(
            "camera.ready",
            requires=[
                ANY(
                    equals("camera.front.ready", True),
                    equals("camera.rear.ready", True),
                )
            ],
        )
    )
    machine.observe("camera.front.ready", False)

    result = machine.evaluate("camera.ready")

    assert result.status == CapabilityStatus.UNKNOWN
    assert result.unknown_paths == ["camera.rear.ready"]
    assert result.blocking[0].children
    child_paths = {child.path for child in result.blocking[0].children}
    assert child_paths == {"camera.front.ready", "camera.rear.ready"}


def test_all_propagates_invalid_child_path() -> None:
    schema = TelemetrySchema()
    schema.define(TelemetryFieldSpec("battery.level_pct", kind="number"))
    schema.define(TelemetryFieldSpec("safety.estop", kind="boolean"))
    machine = ContextMachine(telemetry_schema=schema)
    machine.define_capability(
        capability(
            "operate",
            requires=[
                ALL(
                    gte("battery.level_pct", 20),
                    equals("safety.estop", False),
                )
            ],
        )
    )
    machine.observe("battery.level_pct", "bad")
    machine.observe("safety.estop", False)

    result = machine.evaluate("operate")

    assert result.status == CapabilityStatus.UNKNOWN
    assert result.unknown_paths == ["battery.level_pct"]


def test_evaluator_exception_is_unknown_not_unavailable() -> None:
    @capability(name="custom.evaluator", version="1.0")
    def evaluator(machine: ContextMachine) -> bool:
        raise RuntimeError("sensor parser failed")

    machine = ContextMachine()
    machine.define_capability(evaluator)
    result = machine.evaluate("custom.evaluator")

    assert result.status == CapabilityStatus.UNKNOWN
    assert result.blocking[0].code == "EVALUATOR_ERROR"
    assert result.blocking[0].is_invalid


def test_sense_config_builds_complete_raw_to_capability_pipeline() -> None:
    config = SenseConfig.from_dict(
        {
            "telemetry": {
                "schema": {
                    "fields": [
                        {
                            "path": "battery.level_pct",
                            "kind": "number",
                            "minimum": 0,
                            "maximum": 100,
                        }
                    ]
                },
                "mappings": [
                    {
                        "source": "battery.ratio",
                        "target": "battery.level_pct",
                        "transform": "ratio_to_percent",
                    }
                ],
            },
            "capabilities": [
                {
                    "name": "power.ready",
                    "version": "1.0.0",
                    "requires": [
                        {
                            "op": "gte",
                            "path": "battery.level_pct",
                            "value": 20,
                        }
                    ],
                }
            ],
        }
    )

    machine = config.build_machine(machine_ref="robot-1")
    machine.ingest(
        {"battery": {"ratio": 0.65}},
        normalizer=config.normalizer,
    )

    assert machine.evaluate("power.ready").status == CapabilityStatus.AVAILABLE
