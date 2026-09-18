"""Reusable raw-telemetry transforms."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, cast

from sense_ai.model.observation import JSONValue, is_json_value

TransformCallable = Callable[[JSONValue, Mapping[str, Any]], JSONValue]


@dataclass(frozen=True, slots=True)
class TransformSpec:
    """Named transform plus JSON-compatible parameters."""

    name: str
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_value(cls, value: str | dict[str, Any]) -> TransformSpec:
        if isinstance(value, str):
            return cls(name=value)
        if "name" not in value:
            raise ValueError("transform must be a name or an object with a name")
        return cls(
            name=str(value["name"]),
            params={str(key): item for key, item in value.items() if key != "name"},
        )


class TransformRegistry:
    """Extensible registry of deterministic telemetry transforms."""

    def __init__(self) -> None:
        self._transforms: dict[str, TransformCallable] = {}
        self._register_builtins()

    def register(self, name: str, transform: TransformCallable) -> None:
        if not name:
            raise ValueError("transform name must be non-empty")
        self._transforms[name] = transform

    def apply(self, value: JSONValue, spec: TransformSpec) -> JSONValue:
        try:
            transform = self._transforms[spec.name]
        except KeyError as exc:
            raise ValueError(f"unknown telemetry transform: {spec.name}") from exc
        return transform(value, spec.params)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._transforms))

    def _register_builtins(self) -> None:
        self.register("identity", _identity)
        self.register("scale", _scale)
        self.register("ratio_to_percent", _ratio_to_percent)
        self.register("percent_to_ratio", _percent_to_ratio)
        self.register("fahrenheit_to_celsius", _fahrenheit_to_celsius)
        self.register("celsius_to_fahrenheit", _celsius_to_fahrenheit)
        self.register("enum_map", _enum_map)
        self.register("map_range", _map_range)
        self.register("round", _round_value)


def _number(value: JSONValue) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"expected numeric telemetry, got {type(value).__name__}")
    return float(value)


def _json_value(value: Any) -> JSONValue:
    if not is_json_value(value):
        raise ValueError(
            f"transform produced non-JSON value: {type(value).__name__}"
        )
    return cast(JSONValue, value)


def _identity(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    del params
    return value


def _scale(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    factor = float(params.get("factor", 1.0))
    offset = float(params.get("offset", 0.0))
    return (_number(value) * factor) + offset


def _ratio_to_percent(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    del params
    return _number(value) * 100.0


def _percent_to_ratio(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    del params
    return _number(value) / 100.0


def _fahrenheit_to_celsius(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    del params
    return (_number(value) - 32.0) * (5.0 / 9.0)


def _celsius_to_fahrenheit(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    del params
    return (_number(value) * (9.0 / 5.0)) + 32.0


def _enum_map(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    mapping = params.get("mapping")
    if not isinstance(mapping, dict):
        raise ValueError("enum_map requires a mapping object")
    key = str(value)
    if key not in mapping:
        if "default" in params:
            return _json_value(params["default"])
        raise ValueError(f"no enum mapping for {value!r}")
    return _json_value(mapping[key])


def _map_range(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    raw = _number(value)
    in_min = float(params["in_min"])
    in_max = float(params["in_max"])
    out_min = float(params["out_min"])
    out_max = float(params["out_max"])
    if in_max == in_min:
        raise ValueError("map_range input range cannot have zero width")
    ratio = (raw - in_min) / (in_max - in_min)
    return out_min + ratio * (out_max - out_min)


def _round_value(value: JSONValue, params: Mapping[str, Any]) -> JSONValue:
    digits = int(params.get("digits", 0))
    return round(_number(value), digits)


DEFAULT_TRANSFORMS = TransformRegistry()
