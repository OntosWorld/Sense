"""Reusable, version-aware capability registry and config compiler."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sense_ai.model.capability import CapabilitySpec, capability
from sense_ai.rules import (
    ALL,
    ANY,
    NONE_OF,
    NOT,
    ONLY_ONE,
    Constraint,
    equals,
    exists,
    fresh,
    gt,
    gte,
    in_,
    lt,
    lte,
)


@dataclass(slots=True)
class CapabilityRegistry:
    """Registry of reusable, versioned capability specifications."""

    _specs: dict[str, dict[str, CapabilitySpec]] = field(default_factory=dict)

    def register(self, spec: CapabilitySpec) -> None:
        versions = self._specs.setdefault(spec.name, {})
        versions[spec.version] = spec

    def register_many(self, specs: list[CapabilitySpec]) -> None:
        for spec in specs:
            self.register(spec)

    def get(self, name: str, version: str | None = None) -> CapabilitySpec:
        try:
            versions = self._specs[name]
        except KeyError as exc:
            raise KeyError(f"capability {name!r} is not registered") from exc
        if version is not None:
            try:
                return versions[version]
            except KeyError as exc:
                raise KeyError(
                    f"capability {name!r} has no version {version!r}"
                ) from exc
        return versions[_latest_version(tuple(versions))]

    def versions(self, name: str) -> tuple[str, ...]:
        return tuple(sorted(self._specs.get(name, {}), key=_version_key))

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def install(
        self,
        machine: Any,
        *,
        selections: dict[str, str | None] | None = None,
    ) -> None:
        selected = selections or {name: None for name in self.names}
        for name, version in selected.items():
            machine.define_capability(self.get(name, version))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityRegistry":
        raw_caps = data.get("capabilities", [])
        if not isinstance(raw_caps, list):
            raise ValueError("capabilities must be a list")
        registry = cls()
        for raw in raw_caps:
            if not isinstance(raw, dict):
                raise ValueError("each capability must be an object")
            registry.register(capability_from_dict(raw))
        return registry

    @classmethod
    def from_json_file(cls, path: str | Path) -> "CapabilityRegistry":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("capability config must contain a JSON object")
        return cls.from_dict(raw)


def capability_from_dict(data: dict[str, Any]) -> CapabilitySpec:
    """Compile a declarative capability object into a CapabilitySpec."""
    requires = [_constraint_from_dict(item) for item in _rule_list(data, "requires")]
    degrade = [
        _constraint_from_dict(item) for item in _rule_list(data, "degrade_when")
    ]
    spec = capability(
        str(data["name"]),
        requires=requires,
        degrade_when=degrade,
        version=str(data.get("version", "1.0.0")),
        description=str(data.get("description", "")),
        inputs=_dict_value(data.get("inputs")),
        outputs=_dict_value(data.get("outputs")),
        metadata=_dict_value(data.get("metadata")),
    )
    if not isinstance(spec, CapabilitySpec):
        raise TypeError("compiled capability did not produce CapabilitySpec")
    return spec


def _constraint_from_dict(data: Any) -> Constraint:
    if not isinstance(data, dict):
        raise ValueError("constraint must be an object")
    op = str(data.get("op", "")).lower()

    if op in {"all", "any", "none_of", "only_one"}:
        raw_children = data.get("rules", [])
        if not isinstance(raw_children, list) or not raw_children:
            raise ValueError(f"{op} requires a non-empty rules list")
        children = [_constraint_from_dict(child) for child in raw_children]
        return {
            "all": ALL,
            "any": ANY,
            "none_of": NONE_OF,
            "only_one": ONLY_ONE,
        }[op](*children)

    if op == "not":
        return NOT(_constraint_from_dict(data["rule"]))

    path = str(data.get("path", ""))
    if not path:
        raise ValueError(f"{op or 'constraint'} requires path")

    if op == "equals":
        return equals(path, data.get("value"))
    if op == "gte":
        return gte(path, _number(data["value"]))
    if op == "gt":
        return gt(path, _number(data["value"]))
    if op == "lte":
        return lte(path, _number(data["value"]))
    if op == "lt":
        return lt(path, _number(data["value"]))
    if op == "fresh":
        max_age_ms = data.get("max_age_ms")
        if isinstance(max_age_ms, bool) or not isinstance(max_age_ms, int):
            raise ValueError("fresh requires integer max_age_ms")
        return fresh(path, max_age_ms=max_age_ms)
    if op == "exists":
        return exists(path)
    if op == "in":
        values = data.get("values")
        if not isinstance(values, list):
            raise ValueError("in requires values list")
        return in_(path, values)

    raise ValueError(f"unsupported constraint op: {op!r}")


def _rule_list(data: dict[str, Any], key: str) -> list[Any]:
    raw = data.get(key, [])
    if not isinstance(raw, list):
        raise ValueError(f"{key} must be a list")
    return raw


def _dict_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("expected object")
    return dict(value)


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("numeric constraint requires a number")
    return float(value)


def _version_key(version: str) -> tuple[int, ...] | tuple[str]:
    try:
        return tuple(int(part) for part in version.split("."))
    except ValueError:
        return (version,)


def _latest_version(versions: tuple[str, ...]) -> str:
    if not versions:
        raise KeyError("no capability versions registered")
    return max(versions, key=_version_key)
