"""Typed telemetry field schemas used by Sense ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast

from sense_ai.model.observation import JSONValue, is_json_value

TelemetryKind = Literal[
    "any",
    "number",
    "integer",
    "string",
    "boolean",
    "object",
    "array",
    "null",
]
_TELEMETRY_KINDS = {
    "any",
    "number",
    "integer",
    "string",
    "boolean",
    "object",
    "array",
    "null",
}


@dataclass(frozen=True, slots=True)
class TelemetryValidationIssue:
    """One machine-readable telemetry validation problem."""

    path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class TelemetryFieldSpec:
    """Canonical contract for one Sense telemetry path."""

    path: str
    kind: TelemetryKind = "any"
    nullable: bool = False
    minimum: float | None = None
    maximum: float | None = None
    enum: tuple[JSONValue, ...] | None = None
    ttl_ms: int | None = None
    unit: str | None = None
    description: str = ""

    def validate(self, value: JSONValue) -> tuple[TelemetryValidationIssue, ...]:
        issues: list[TelemetryValidationIssue] = []

        if value is None:
            if self.nullable or self.kind in ("any", "null"):
                return ()
            return (
                TelemetryValidationIssue(
                    path=self.path,
                    code="NULL_NOT_ALLOWED",
                    message=f"{self.path} does not allow null values",
                ),
            )

        if self.kind != "any" and not _matches_kind(value, self.kind):
            return (
                TelemetryValidationIssue(
                    path=self.path,
                    code="INVALID_TYPE",
                    message=(
                        f"{self.path} expected {self.kind}, "
                        f"received {type(value).__name__}"
                    ),
                ),
            )

        if isinstance(value, (int, float)) and not isinstance(value, bool):
            numeric = float(value)
            if self.minimum is not None and numeric < self.minimum:
                issues.append(
                    TelemetryValidationIssue(
                        path=self.path,
                        code="BELOW_MINIMUM",
                        message=f"{self.path} must be >= {self.minimum}",
                    )
                )
            if self.maximum is not None and numeric > self.maximum:
                issues.append(
                    TelemetryValidationIssue(
                        path=self.path,
                        code="ABOVE_MAXIMUM",
                        message=f"{self.path} must be <= {self.maximum}",
                    )
                )

        if self.enum is not None and value not in self.enum:
            issues.append(
                TelemetryValidationIssue(
                    path=self.path,
                    code="NOT_IN_ENUM",
                    message=f"{self.path} value is not in the allowed set",
                )
            )

        return tuple(issues)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryFieldSpec:
        raw_kind = str(data.get("kind", "any"))
        if raw_kind not in _TELEMETRY_KINDS:
            raise ValueError(f"unsupported telemetry kind: {raw_kind!r}")
        kind = cast(TelemetryKind, raw_kind)

        enum_raw = data.get("enum")
        enum: tuple[JSONValue, ...] | None = None
        if enum_raw is not None:
            if not isinstance(enum_raw, list):
                raise ValueError("telemetry enum must be a list")
            if not all(is_json_value(item) for item in enum_raw):
                raise ValueError("telemetry enum values must be JSON-compatible")
            enum = tuple(cast(JSONValue, item) for item in enum_raw)

        return cls(
            path=str(data["path"]),
            kind=kind,
            nullable=bool(data.get("nullable", False)),
            minimum=_optional_float(data.get("minimum")),
            maximum=_optional_float(data.get("maximum")),
            enum=enum,
            ttl_ms=_optional_int(data.get("ttl_ms")),
            unit=str(data["unit"]) if data.get("unit") is not None else None,
            description=str(data.get("description", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "nullable": self.nullable,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "enum": list(self.enum) if self.enum is not None else None,
            "ttl_ms": self.ttl_ms,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass(slots=True)
class TelemetrySchema:
    """Registry of canonical telemetry paths and their validation contracts."""

    strict: bool = False
    _fields: dict[str, TelemetryFieldSpec] = field(default_factory=dict)

    def define(self, spec: TelemetryFieldSpec) -> None:
        self._fields[spec.path] = spec

    def define_many(self, specs: list[TelemetryFieldSpec]) -> None:
        for spec in specs:
            self.define(spec)

    def get(self, path: str) -> TelemetryFieldSpec | None:
        return self._fields.get(path)

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(self._fields)

    def validate(
        self,
        path: str,
        value: JSONValue,
    ) -> tuple[TelemetryValidationIssue, ...]:
        spec = self.get(path)
        if spec is None:
            if not self.strict:
                return ()
            return (
                TelemetryValidationIssue(
                    path=path,
                    code="UNDECLARED_PATH",
                    message=f"{path} is not declared in the telemetry schema",
                ),
            )
        return spec.validate(value)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetrySchema:
        schema = cls(strict=bool(data.get("strict", False)))
        fields = data.get("fields", [])
        if not isinstance(fields, list):
            raise ValueError("telemetry schema fields must be a list")
        schema.define_many(
            [
                TelemetryFieldSpec.from_dict(item)
                for item in fields
                if isinstance(item, dict)
            ]
        )
        return schema

    @classmethod
    def from_json_file(cls, path: str | Path) -> TelemetrySchema:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("telemetry schema file must contain a JSON object")
        return cls.from_dict(raw)

    def to_dict(self) -> dict[str, Any]:
        return {
            "strict": self.strict,
            "fields": [spec.to_dict() for spec in self._fields.values()],
        }


def _matches_kind(value: JSONValue, kind: TelemetryKind) -> bool:
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "boolean":
        return isinstance(value, bool)
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "null":
        return value is None
    return True


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected numeric value")
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("expected integer value")
    return value
