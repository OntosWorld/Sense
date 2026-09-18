"""Versioned, language-neutral machine context snapshots."""

from __future__ import annotations

import fnmatch
import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sense_ai.errors import InvalidRuleError, SerializationError

from .observation import JSONValue, TelemetryObservation
from .result import CapabilityResult, CapabilityStatus

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CapabilitySnapshot:
    """Serialized point-in-time result for one capability."""

    name: str
    status: CapabilityStatus
    blocking: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    unknown_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reasons": [*self.blocking, *self.warnings],
            "unknown_paths": list(self.unknown_paths),
        }

    @classmethod
    def from_result(cls, result: CapabilityResult) -> "CapabilitySnapshot":
        return cls(
            name=result.name,
            status=result.status,
            blocking=[reason.to_dict() for reason in result.blocking],
            warnings=[reason.to_dict() for reason in result.warnings],
            unknown_paths=list(result.unknown_paths),
        )

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "CapabilitySnapshot":
        try:
            status = CapabilityStatus(data["status"])
        except (KeyError, ValueError) as exc:
            raise SerializationError(
                f"Invalid capability status for {name!r}: {exc}",
                schema_version="1.0",
            ) from exc

        reasons = data.get("reasons", [])
        if not isinstance(reasons, list):
            raise SerializationError(
                f"Capability reasons for {name!r} must be an array",
                schema_version="1.0",
            )

        blocking: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        for reason in reasons:
            if not isinstance(reason, dict):
                raise SerializationError(
                    f"Capability reason for {name!r} must be an object",
                    schema_version="1.0",
                )
            if reason.get("severity") == "warning":
                warnings.append(reason)
            else:
                blocking.append(reason)

        unknown_paths = data.get("unknown_paths", [])
        if not isinstance(unknown_paths, list):
            raise SerializationError(
                f"unknown_paths for {name!r} must be an array",
                schema_version="1.0",
            )

        return cls(
            name=name,
            status=status,
            blocking=blocking,
            warnings=warnings,
            unknown_paths=[str(path) for path in unknown_paths],
        )


@dataclass(slots=True)
class ContextSnapshot:
    """Canonical serializable output of the Sense runtime."""

    schema_version: str = "1.0"
    machine_ref: str | None = None
    peaq_did: str | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    observations: dict[str, TelemetryObservation] = field(default_factory=dict)
    capabilities: dict[str, CapabilitySnapshot] = field(default_factory=dict)
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        observations = list(self.observations.values())
        latest = max((item.observed_at for item in observations), default=None)
        state: dict[str, JSONValue] = {
            observation.path: observation.value for observation in observations
        }
        return {
            "schema_version": self.schema_version,
            "machine": {
                "ref": self.machine_ref,
                "peaq_did": self.peaq_did,
            },
            "generated_at": self.generated_at.isoformat(),
            "latest_observation_at": latest.isoformat() if latest else None,
            "state": state,
            "observations": [
                observation.to_dict() for observation in observations
            ],
            "capabilities": {
                name: capability.to_dict()
                for name, capability in self.capabilities.items()
            },
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ContextSnapshot":
        try:
            machine = data["machine"]
            generated_raw = data["generated_at"]
        except KeyError as exc:
            raise SerializationError(
                f"Missing required snapshot field: {exc}",
                schema_version=data.get("schema_version"),
            ) from exc

        if not isinstance(machine, dict):
            raise SerializationError(
                "machine must be an object",
                schema_version=data.get("schema_version"),
            )
        if not isinstance(generated_raw, str):
            raise SerializationError(
                "generated_at must be an ISO 8601 string",
                schema_version=data.get("schema_version"),
            )

        try:
            generated_at = datetime.fromisoformat(
                generated_raw.replace("Z", "+00:00")
            )
        except ValueError as exc:
            raise SerializationError(
                f"Invalid generated_at value: {generated_raw!r}",
                schema_version=data.get("schema_version"),
            ) from exc

        observations: dict[str, TelemetryObservation] = {}
        for raw_observation in data.get("observations", []):
            if not isinstance(raw_observation, dict):
                raise SerializationError(
                    "observations entries must be objects",
                    schema_version=data.get("schema_version"),
                )
            observation = TelemetryObservation.from_dict(raw_observation)
            observations[observation.path] = observation

        capabilities: dict[str, CapabilitySnapshot] = {}
        raw_capabilities = data.get("capabilities", {})
        if not isinstance(raw_capabilities, dict):
            raise SerializationError(
                "capabilities must be an object",
                schema_version=data.get("schema_version"),
            )
        for name, raw_capability in raw_capabilities.items():
            if not isinstance(raw_capability, dict):
                raise SerializationError(
                    f"Capability {name!r} must be an object",
                    schema_version=data.get("schema_version"),
                )
            capabilities[name] = CapabilitySnapshot.from_dict(name, raw_capability)

        return cls(
            schema_version=str(data.get("schema_version", "1.0")),
            machine_ref=machine.get("ref"),
            peaq_did=machine.get("peaq_did"),
            generated_at=generated_at,
            observations=observations,
            capabilities=capabilities,
            trace_id=data.get("trace_id"),
        )

    def to_json(self, *, indent: int | None = None) -> str:
        """Serialize the snapshot to JSON."""
        try:
            return json.dumps(
                self.to_dict(),
                separators=None if indent is not None else (",", ":"),
                indent=indent,
            )
        except (TypeError, ValueError) as exc:
            raise SerializationError(
                f"Snapshot cannot be encoded as JSON: {exc}",
                schema_version=self.schema_version,
            ) from exc

    @classmethod
    def from_json(cls, value: str) -> "ContextSnapshot":
        """Parse a serialized snapshot."""
        try:
            data = json.loads(value)
        except json.JSONDecodeError as exc:
            raise SerializationError(
                f"Invalid JSON: {exc}",
                schema_version=None,
            ) from exc
        if not isinstance(data, dict):
            raise SerializationError(
                "Snapshot root must be an object",
                schema_version=None,
            )
        return cls.from_dict(data)

    @staticmethod
    def _matches(path: str, patterns: Sequence[str]) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)

    def redact(
        self,
        *,
        keep_observations: Sequence[str] | None = None,
        drop_observations: Sequence[str] | None = None,
        keep_capabilities: Sequence[str] | None = None,
        drop_capabilities: Sequence[str] | None = None,
    ) -> "ContextSnapshot":
        """Return a filtered copy for data minimization."""
        if keep_observations is not None and drop_observations is not None:
            raise InvalidRuleError(
                "keep_observations and drop_observations are mutually exclusive"
            )
        if keep_capabilities is not None and drop_capabilities is not None:
            raise InvalidRuleError(
                "keep_capabilities and drop_capabilities are mutually exclusive"
            )

        observations: dict[str, TelemetryObservation] = {}
        for path, observation in self.observations.items():
            if keep_observations is not None:
                if self._matches(path, keep_observations):
                    observations[path] = observation
            elif drop_observations is not None:
                if not self._matches(path, drop_observations):
                    observations[path] = observation
            else:
                observations[path] = observation

        capabilities: dict[str, CapabilitySnapshot] = {}
        for name, capability in self.capabilities.items():
            if keep_capabilities is not None:
                if self._matches(name, keep_capabilities):
                    capabilities[name] = capability
            elif drop_capabilities is not None:
                if not self._matches(name, drop_capabilities):
                    capabilities[name] = capability
            else:
                capabilities[name] = capability

        return ContextSnapshot(
            schema_version=self.schema_version,
            machine_ref=self.machine_ref,
            peaq_did=self.peaq_did,
            generated_at=self.generated_at,
            observations=observations,
            capabilities=capabilities,
            trace_id=self.trace_id,
        )

    def local_view(
        self,
        *,
        drop_observations: Sequence[str] | None = None,
        drop_capabilities: Sequence[str] | None = None,
    ) -> "ContextSnapshot":
        """Return an internal view with the peaq DID stripped."""
        result = self.redact(
            drop_observations=drop_observations,
            drop_capabilities=drop_capabilities,
        )
        result.peaq_did = None
        return result

    def publishable_view(
        self,
        *,
        keep_observations: Sequence[str] | None = None,
        keep_capabilities: Sequence[str] | None = None,
    ) -> "ContextSnapshot":
        """Return an external view.

        No raw observation is included unless it is explicitly allowlisted.
        """
        result = self.redact(
            keep_observations=(
                list(keep_observations)
                if keep_observations is not None
                else []
            ),
            keep_capabilities=keep_capabilities,
        )
        result.peaq_did = None
        return result
