"""Single-file Sense configuration for schemas, mappings and capabilities."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sense_ai.model.machine import ContextMachine
from sense_ai.registry import CapabilityRegistry
from sense_ai.telemetry import TelemetryNormalizer, TelemetrySchema


@dataclass(frozen=True, slots=True)
class SenseConfig:
    """Compiled SDK configuration."""

    telemetry_schema: TelemetrySchema
    normalizer: TelemetryNormalizer
    capabilities: CapabilityRegistry

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SenseConfig":
        telemetry_raw = data.get("telemetry", {})
        if not isinstance(telemetry_raw, dict):
            raise ValueError("telemetry must be an object")

        schema_raw = telemetry_raw.get("schema", {})
        if not isinstance(schema_raw, dict):
            raise ValueError("telemetry.schema must be an object")
        schema = TelemetrySchema.from_dict(schema_raw)

        mapping_raw = {"mappings": telemetry_raw.get("mappings", [])}
        normalizer = TelemetryNormalizer.from_dict(mapping_raw, schema=schema)

        registry = CapabilityRegistry.from_dict(
            {"capabilities": data.get("capabilities", [])}
        )
        return cls(
            telemetry_schema=schema,
            normalizer=normalizer,
            capabilities=registry,
        )

    @classmethod
    def from_json_file(cls, path: str | Path) -> "SenseConfig":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Sense config must contain a JSON object")
        return cls.from_dict(raw)

    def build_machine(
        self,
        *,
        machine_ref: str | None = None,
        peaq_did: str | None = None,
        trace_id: str | None = None,
    ) -> ContextMachine:
        machine = ContextMachine(
            machine_ref=machine_ref,
            peaq_did=peaq_did,
            trace_id=trace_id,
            telemetry_schema=self.telemetry_schema,
        )
        self.capabilities.install(machine)
        return machine
