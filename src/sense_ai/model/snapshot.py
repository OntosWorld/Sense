"""ContextSnapshot — a versioned point-in-time machine state, per PRD §9.2."""

from __future__ import annotations

import fnmatch
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from sense_ai.errors import InvalidRuleError, SerializationError

from .observation import TelemetryObservation
from .result import CapabilityResult, CapabilityStatus

logger = logging.getLogger(__name__)


@dataclass
class CapabilitySnapshot:
    """
    Per-capability slice inside a :class:`ContextSnapshot`.

    Mirrors the ``"capabilities"`` block in the JSON example in PRD §9.2::

        {
          "warehouse.pick": {
            "status": "DEGRADED",
            "reasons": [{"code": "PAYLOAD_MARGIN_LOW", "path": "..."}]
          }
        }
    """

    name: str
    status: CapabilityStatus
    blocking: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    unknown_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete capability evaluation contract."""
        reasons: list[dict[str, Any]] = list(self.blocking) + list(self.warnings)
        return {
            "status": self.status.value,
            "blocking": list(self.blocking),
            "warnings": list(self.warnings),
            "unknown_paths": list(self.unknown_paths),
            "reasons": reasons,
        }

    @classmethod
    def from_result(cls, result: CapabilityResult) -> CapabilitySnapshot:
        return cls(
            name=result.name,
            status=result.status,
            blocking=[r.to_dict() for r in result.blocking],
            warnings=[r.to_dict() for r in result.warnings],
            unknown_paths=result.unknown_paths,
        )


@dataclass
class ContextSnapshot:
    """
    A versioned point-in-time representation of known machine context, per PRD §9.2.

    This is the canonical serializable output of the Sense runtime.  It is
    local-first; publishing to peaq or other external systems requires an
    explicit adapter call (PRD §8.2, §11.2).

    Attributes
    ----------
    schema_version : str
        Always ``"1.0"`` for v1.  Breaking schema changes increment the major
        version independently from the SDK version (PRD §17.3).
    machine_ref : str | None
        Developer-supplied machine identifier.
    peaq_did : str | None
        peaq decentralized identifier bound to this machine (PRD §8.1).
    generated_at : datetime
        When this snapshot was produced (UTC).
    observations : dict[str, TelemetryObservation]
        All currently held telemetry observations, keyed by path.
    capabilities : dict[str, CapabilitySnapshot]
        Evaluated capability statuses keyed by name.
    trace_id : str | None
        Optional distributed-trace identifier for correlating snapshots.
    """

    schema_version: str = "1.0"
    machine_ref: str | None = None
    peaq_did: str | None = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    observations: dict[str, TelemetryObservation] = field(default_factory=dict)
    capabilities: dict[str, CapabilitySnapshot] = field(default_factory=dict)
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize to a dict matching the JSON representation in PRD §9.2.

        The ``observations`` block uses dot-notation paths as keys for
        readability; the JSON Schema representation flattens each observation
        individually.
        """
        obs_list = list(self.observations.values())
        latest = max((o.observed_at for o in obs_list), default=None)

        return {
            "schema_version": self.schema_version,
            "machine": {
                "ref": self.machine_ref,
                "peaq_did": self.peaq_did,
            },
            "generated_at": self.generated_at.isoformat(),
            "latest_observation_at": latest.isoformat() if latest else None,
            "state": {obs.path: obs.value for obs in obs_list},
            "observations": [obs.to_dict() for obs in obs_list],
            "capabilities": {
                name: snap.to_dict() for name, snap in self.capabilities.items()
            },
            "trace_id": self.trace_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextSnapshot:
        """
        Reconstruct a snapshot from a parsed JSON dict.

        Raises
        ------
        SerializationError
            When ``data`` is missing required fields or contains unparseable values.
        """
        try:
            machine_block = data["machine"]
            generated_raw = data["generated_at"]
        except KeyError as exc:
            raise SerializationError(
                f"Missing required snapshot field: {exc}",
                schema_version=data.get("schema_version"),
            ) from exc

        try:
            if isinstance(generated_raw, str):
                generated_at = datetime.fromisoformat(
                    generated_raw.replace("Z", "+00:00")
                )
            else:
                generated_at = generated_raw
        except (ValueError, TypeError) as exc:
            raise SerializationError(
                f"Invalid generated_at value {generated_raw!r}: {exc}",
                schema_version=data.get("schema_version"),
            ) from exc

        raw_obs: list[dict[str, Any]] = data.get("observations", [])
        observations: dict[str, TelemetryObservation] = {}
        for obs_dict in raw_obs:
            obs = TelemetryObservation.from_dict(obs_dict)
            observations[obs.path] = obs

        cap_block: dict[str, dict[str, Any]] = data.get("capabilities", {})
        capabilities: dict[str, CapabilitySnapshot] = {}
        for name, cap_dict in cap_block.items():
            try:
                reasons = cap_dict.get("reasons", [])
                blocking = cap_dict.get("blocking")
                warnings = cap_dict.get("warnings")
                if blocking is None and warnings is None:
                    blocking = [
                        reason
                        for reason in reasons
                        if reason.get("severity") == "blocking"
                    ]
                    warnings = [
                        reason
                        for reason in reasons
                        if reason.get("severity") == "warning"
                    ]
                capabilities[name] = CapabilitySnapshot(
                    name=name,
                    status=CapabilityStatus(cap_dict["status"]),
                    blocking=blocking or [],
                    warnings=warnings or [],
                    unknown_paths=cap_dict.get("unknown_paths", []),
                )
            except (KeyError, ValueError) as exc:
                raise SerializationError(
                    f"Invalid capability block for {name!r}: {exc}",
                    schema_version=data.get("schema_version"),
                ) from exc

        return cls(
            schema_version=data.get("schema_version", "1.0"),
            machine_ref=machine_block.get("ref"),
            peaq_did=machine_block.get("peaq_did"),
            generated_at=generated_at,
            observations=observations,
            capabilities=capabilities,
            trace_id=data.get("trace_id"),
        )

    def to_json(self) -> str:
        """
        Encode this snapshot to a compact JSON string.

        Raises
        ------
        SerializationError
            When the snapshot cannot be serialised to JSON.
        """
        try:
            return json.dumps(self.to_dict(), separators=(",", ":"))
        except TypeError as exc:
            raise SerializationError(
                f"Snapshot cannot be encoded as JSON: {exc}",
                schema_version=self.schema_version,
            ) from exc

    @classmethod
    def from_json(cls, s: str) -> ContextSnapshot:
        """
        Decode a snapshot from a JSON string.

        Raises
        ------
        SerializationError
            When the string is not valid JSON or the data is not a valid snapshot.
        """
        try:
            data = json.loads(s)
        except json.JSONDecodeError as exc:
            raise SerializationError(
                f"Invalid JSON: {exc}",
                schema_version=None,
            ) from exc
        return cls.from_dict(data)

    # ------------------------------------------------------------------
    # Data minimisation — FR-13
    # ------------------------------------------------------------------

    @staticmethod
    def _match_path(path: str, patterns: Sequence[str]) -> bool:
        """Return True if ``path`` matches any glob ``patterns``."""
        return any(fnmatch.fnmatch(path, p) for p in patterns)

    def redact(
        self,
        *,
        keep_observations: Sequence[str] | None = None,
        drop_observations: Sequence[str] | None = None,
        keep_capabilities: Sequence[str] | None = None,
        drop_capabilities: Sequence[str] | None = None,
    ) -> ContextSnapshot:
        """
        Return a **new** snapshot with a filtered view of observations and capabilities.

        This is the primary data-minimisation primitive (FR-13).  It is safe to
        call on any snapshot — the original is never mutated.

        Parameters
        ----------
        keep_observations : Sequence[str], optional
            Allowlist of observation paths (glob patterns supported, e.g. ``"sensor.*"``).
            When set, **only** observations whose paths match at least one pattern are
            retained.  All others are dropped.
        drop_observations : Sequence[str], optional
            Denylist of observation paths (glob patterns supported).
            Observations whose paths match any pattern are removed.
            Applied after ``keep_observations``.
        keep_capabilities : Sequence[str], optional
            Allowlist of capability names (glob patterns supported).
            When set, only matching capabilities are retained.
        drop_capabilities : Sequence[str], optional
            Denylist of capability names (glob patterns supported).
            Matching capabilities are removed.  Applied after ``keep_capabilities``.

        Returns
        -------
        ContextSnapshot
            A new snapshot with a subset of the original data.

        Raises
        ------
        InvalidRuleError
            When both ``keep_observations`` and ``drop_observations`` are provided,
            or when both ``keep_capabilities`` and ``drop_capabilities`` are provided.

        Notes
        -----
        - ``keep_*`` and ``drop_*`` are mutually exclusive per domain
          (observations / capabilities).
        - ``peaq_did`` is **not** included in observations; use ``local_view()``
          to strip it before sharing externally, or ``publishable_view()`` for a
          pre-configured safe public view.

        Example
        -------
        >>> snap = machine.snapshot()
        >>> # Only publish battery and sensor data
        >>> pub = snap.redact(keep_observations=["battery.*", "sensor.*"])
        >>> # Share everything except internal paths
        >>> shared = snap.redact(drop_observations=["*.internal.*"])
        """
        if keep_observations is not None and drop_observations is not None:
            raise InvalidRuleError(
                "keep_observations and drop_observations are mutually exclusive",
                capability_path=None,
            )
        if keep_capabilities is not None and drop_capabilities is not None:
            raise InvalidRuleError(
                "keep_capabilities and drop_capabilities are mutually exclusive",
                capability_path=None,
            )

        # Filter observations
        filtered_obs: dict[str, TelemetryObservation] = {}
        for path, obs in self.observations.items():
            if keep_observations is not None:
                if self._match_path(path, keep_observations):
                    filtered_obs[path] = obs
            elif drop_observations is not None:
                if not self._match_path(path, drop_observations):
                    filtered_obs[path] = obs
            else:
                filtered_obs[path] = obs

        # Filter capabilities
        filtered_caps: dict[str, CapabilitySnapshot] = {}
        for name, cap in self.capabilities.items():
            if keep_capabilities is not None:
                if self._match_path(name, keep_capabilities):
                    filtered_caps[name] = cap
            elif drop_capabilities is not None:
                if not self._match_path(name, drop_capabilities):
                    filtered_caps[name] = cap
            else:
                filtered_caps[name] = cap

        logger.debug(
            "ContextSnapshot.redact: kept %d/%d observations, %d/%d capabilities",
            len(filtered_obs),
            len(self.observations),
            len(filtered_caps),
            len(self.capabilities),
        )
        return ContextSnapshot(
            schema_version=self.schema_version,
            machine_ref=self.machine_ref,
            peaq_did=self.peaq_did,
            generated_at=self.generated_at,
            observations=filtered_obs,
            capabilities=filtered_caps,
            trace_id=self.trace_id,
        )

    def local_view(
        self,
        *,
        drop_observations: Sequence[str] | None = None,
        drop_capabilities: Sequence[str] | None = None,
    ) -> ContextSnapshot:
        """
        Return a snapshot suitable for local/internal processing.

        ``local_view()`` strips the ``peaq_did`` to prevent accidental leakage,
        then applies any additional denylist filters.  Use this when the snapshot
        is consumed inside the same trust boundary (e.g. logging, local caching).

        Parameters
        ----------
        drop_observations : Sequence[str], optional
            Additional observation paths (glob patterns) to exclude.
        drop_capabilities : Sequence[str], optional
            Additional capability names (glob patterns) to exclude.

        Returns
        -------
        ContextSnapshot
            A new snapshot with ``peaq_did`` cleared and denylists applied.

        See Also
        --------
        redact : Full allowlist / denylist control.
        publishable_view : Snapshot view safe for external publication.
        """
        result = self.redact(
            drop_observations=drop_observations,
            drop_capabilities=drop_capabilities,
        )
        return ContextSnapshot(
            schema_version=result.schema_version,
            machine_ref=result.machine_ref,
            peaq_did=None,
            generated_at=result.generated_at,
            observations=result.observations,
            capabilities=result.capabilities,
            trace_id=result.trace_id,
        )

    def publishable_view(
        self,
        *,
        keep_observations: Sequence[str] | None = None,
        keep_capabilities: Sequence[str] | None = None,
    ) -> ContextSnapshot:
        """
        Return a snapshot view safe for external publication.

        ``publishable_view()`` strips ``peaq_did`` and applies allowlists (if given)
        to produce a snapshot suitable for sending to peaq, Machine Markets, or any
        external system.

        Parameters
        ----------
        keep_observations : Sequence[str], optional
            Restrict published observations to paths matching these patterns.
        keep_capabilities : Sequence[str], optional
            Restrict published capabilities to names matching these patterns.

        Returns
        -------
        ContextSnapshot
            A new snapshot with ``peaq_did`` cleared and allowlists applied.

        See Also
        --------
        redact : Full allowlist / denylist control.
        local_view : Snapshot view for internal processing.
        """
        # External publication is privacy-preserving by default: callers must
        # explicitly allow observation paths. Capability results remain included.
        observation_allowlist: Sequence[str] = (
            () if keep_observations is None else keep_observations
        )
        result = self.redact(
            keep_observations=observation_allowlist,
            keep_capabilities=keep_capabilities,
        )
        return ContextSnapshot(
            schema_version=result.schema_version,
            machine_ref=result.machine_ref,
            peaq_did=None,
            generated_at=result.generated_at,
            observations=result.observations,
            capabilities=result.capabilities,
            trace_id=result.trace_id,
        )
