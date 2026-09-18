"""Raw payload to canonical Sense observation normalization."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from sense_ai.model.observation import (
    JSONValue,
    TelemetryObservation,
    is_json_value,
)
from sense_ai.telemetry.schema import TelemetrySchema
from sense_ai.telemetry.transforms import (
    DEFAULT_TRANSFORMS,
    TransformRegistry,
    TransformSpec,
)

if TYPE_CHECKING:
    from sense_ai.model.machine import ContextMachine

_MISSING = object()


@dataclass(frozen=True, slots=True)
class NormalizationIssue:
    """One problem encountered while converting raw telemetry."""

    source_path: str
    target_path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_path": self.source_path,
            "target_path": self.target_path,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class TelemetryMapping:
    """Map one raw payload path to one canonical Sense path."""

    source_path: str
    target_path: str
    transforms: tuple[TransformSpec, ...] = ()
    ttl_ms: int | None = None
    source: str | None = None
    required: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TelemetryMapping:
        transform_values: list[str | dict[str, Any]] = []
        raw_transform = data.get("transform")
        if isinstance(raw_transform, (str, dict)):
            transform_values.append(raw_transform)
        raw_many = data.get("transforms", [])
        if isinstance(raw_many, list):
            transform_values.extend(
                item for item in raw_many if isinstance(item, (str, dict))
            )
        transforms = tuple(
            TransformSpec.from_value(item) for item in transform_values
        )
        ttl = data.get("ttl_ms")
        if ttl is not None and (isinstance(ttl, bool) or not isinstance(ttl, int)):
            raise ValueError("mapping ttl_ms must be an integer")
        return cls(
            source_path=str(data["source"]),
            target_path=str(data["target"]),
            transforms=transforms,
            ttl_ms=ttl,
            source=str(data["source_name"]) if data.get("source_name") else None,
            required=bool(data.get("required", False)),
        )


@dataclass(slots=True)
class NormalizationResult:
    """Observations and issues produced from one raw payload."""

    observations: list[TelemetryObservation] = field(default_factory=list)
    issues: list[NormalizationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


class TelemetryNormalizer:
    """Deterministically map raw OEM/transport payloads into Sense observations."""

    def __init__(
        self,
        mappings: Sequence[TelemetryMapping],
        *,
        schema: TelemetrySchema | None = None,
        transforms: TransformRegistry | None = None,
    ) -> None:
        self._mappings = tuple(mappings)
        self._schema = schema
        self._transforms = transforms or DEFAULT_TRANSFORMS

    @property
    def mappings(self) -> tuple[TelemetryMapping, ...]:
        return self._mappings

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        schema: TelemetrySchema | None = None,
        transforms: TransformRegistry | None = None,
    ) -> TelemetryNormalizer:
        raw_mappings = data.get("mappings", [])
        if not isinstance(raw_mappings, list):
            raise ValueError("normalizer mappings must be a list")
        mappings = [
            TelemetryMapping.from_dict(item)
            for item in raw_mappings
            if isinstance(item, dict)
        ]
        return cls(mappings, schema=schema, transforms=transforms)

    @classmethod
    def from_json_file(
        cls,
        path: str | Path,
        *,
        schema: TelemetrySchema | None = None,
        transforms: TransformRegistry | None = None,
    ) -> TelemetryNormalizer:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("normalizer config must contain a JSON object")
        return cls.from_dict(raw, schema=schema, transforms=transforms)

    def normalize(
        self,
        payload: Mapping[str, Any] | Any,
        *,
        observed_at: datetime | None = None,
        received_at: datetime | None = None,
        source: str | None = None,
    ) -> NormalizationResult:
        now = datetime.now(timezone.utc)
        result = NormalizationResult()

        for mapping in self._mappings:
            raw_value = _extract(payload, mapping.source_path)
            if raw_value is _MISSING:
                if mapping.required:
                    result.issues.append(
                        NormalizationIssue(
                            source_path=mapping.source_path,
                            target_path=mapping.target_path,
                            code="MISSING_SOURCE_FIELD",
                            message=(
                                f"required source field "
                                f"{mapping.source_path!r} is missing"
                            ),
                        )
                    )
                continue

            value: Any = raw_value
            validation_errors: list[str] = []

            for transform in mapping.transforms:
                try:
                    value = self._transforms.apply(
                        _as_json_value(value),
                        transform,
                    )
                except Exception as exc:
                    validation_errors.append(
                        f"TRANSFORM_{transform.name.upper()}: {exc}"
                    )
                    result.issues.append(
                        NormalizationIssue(
                            source_path=mapping.source_path,
                            target_path=mapping.target_path,
                            code="TRANSFORM_ERROR",
                            message=str(exc),
                        )
                    )
                    break

            if not is_json_value(value):
                validation_errors.append(
                    f"INVALID_JSON_VALUE: {type(value).__name__}"
                )
                normalized_value: JSONValue = None
            else:
                normalized_value = cast(JSONValue, value)

            if not validation_errors and self._schema is not None:
                issues = self._schema.validate(
                    mapping.target_path,
                    normalized_value,
                )
                validation_errors.extend(
                    f"{issue.code}: {issue.message}" for issue in issues
                )
                result.issues.extend(
                    NormalizationIssue(
                        source_path=mapping.source_path,
                        target_path=mapping.target_path,
                        code=issue.code,
                        message=issue.message,
                    )
                    for issue in issues
                )

            spec = self._schema.get(mapping.target_path) if self._schema else None
            ttl_ms = (
                mapping.ttl_ms
                if mapping.ttl_ms is not None
                else spec.ttl_ms
                if spec is not None
                else None
            )

            result.observations.append(
                TelemetryObservation(
                    path=mapping.target_path,
                    value=normalized_value,
                    observed_at=observed_at or now,
                    received_at=received_at or now,
                    source=mapping.source or source,
                    ttl_ms=ttl_ms,
                    validation_errors=tuple(validation_errors),
                )
            )

        return result

    def ingest(
        self,
        machine: ContextMachine,
        payload: Mapping[str, Any] | Any,
        **kwargs: Any,
    ) -> NormalizationResult:
        result = self.normalize(payload, **kwargs)
        for observation in result.observations:
            machine.observe(observation)
        return result


def _extract(payload: Any, path: str) -> Any:
    current = payload
    for segment in path.split("."):
        if isinstance(current, Mapping):
            if segment not in current:
                return _MISSING
            current = current[segment]
            continue
        if isinstance(current, (list, tuple)) and segment.isdigit():
            index = int(segment)
            if index >= len(current):
                return _MISSING
            current = current[index]
            continue
        if not hasattr(current, segment):
            return _MISSING
        current = getattr(current, segment)
    return current


def _as_json_value(value: Any) -> JSONValue:
    if not is_json_value(value):
        raise ValueError(f"non-JSON telemetry value: {type(value).__name__}")
    return cast(JSONValue, value)
