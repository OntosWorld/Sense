"""ContextMachine: local-first physical machine context and capability engine."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast

from sense_ai.errors import UnknownCapabilityError
from sense_ai.model.capability import CapabilitySpec
from sense_ai.model.observation import (
    JSONValue,
    TelemetryObservation,
    is_json_value,
)
from sense_ai.model.result import (
    CapabilityResult,
    CapabilityStatus,
    ConstraintResult,
    ContextTransition,
)
from sense_ai.model.snapshot import CapabilitySnapshot, ContextSnapshot
from sense_ai.rules import ObservationStore
from sense_ai.telemetry import (
    NormalizationResult,
    TelemetryFieldSpec,
    TelemetryNormalizer,
    TelemetrySchema,
)

if TYPE_CHECKING:
    from sense_ai.events import EventBus

logger = logging.getLogger(__name__)
_UNSET = object()

TransitionCallback = Callable[[ContextTransition], None]


class _DictStore(ObservationStore):
    """In-memory current-state observation store."""

    __slots__ = ("_observations",)

    def __init__(self) -> None:
        self._observations: dict[str, TelemetryObservation] = {}

    def set(self, observation: TelemetryObservation) -> None:
        self._observations[observation.path] = observation

    def get(self, path: str) -> TelemetryObservation | None:
        return self._observations.get(path)

    def all(self) -> dict[str, TelemetryObservation]:
        return dict(self._observations)


class ContextMachine:
    """Evaluate what a physical machine can do from its current telemetry."""

    __slots__ = (
        "_machine_ref",
        "_peaq_did",
        "_trace_id",
        "_store",
        "_telemetry_schema",
        "_capabilities",
        "_last_result",
        "_last_snapshot",
        "_transitions",
        "_transition_handlers",
        "_event_bus",
        "_warnings",
    )

    def __init__(
        self,
        machine_ref: str | None = None,
        peaq_did: str | None = None,
        trace_id: str | None = None,
        event_bus: EventBus | None = None,
        telemetry_schema: TelemetrySchema | None = None,
    ) -> None:
        self._machine_ref = machine_ref
        self._peaq_did = peaq_did
        self._trace_id = trace_id
        self._store = _DictStore()
        self._telemetry_schema = telemetry_schema or TelemetrySchema()
        self._capabilities: dict[str, CapabilitySpec] = {}
        self._last_result: dict[str, CapabilityResult] = {}
        self._last_snapshot: ContextSnapshot | None = None
        self._transitions: list[ContextTransition] = []
        self._transition_handlers: dict[str, list[TransitionCallback]] = {}
        self._event_bus = event_bus
        self._warnings: list[str] = []

    @property
    def machine_ref(self) -> str | None:
        return self._machine_ref

    @property
    def peaq_did(self) -> str | None:
        return self._peaq_did

    @property
    def observations(self) -> dict[str, TelemetryObservation]:
        return self._store.all()

    @property
    def telemetry_schema(self) -> TelemetrySchema:
        return self._telemetry_schema

    @property
    def capability_names(self) -> tuple[str, ...]:
        return tuple(self._capabilities)

    @property
    def last_snapshot(self) -> ContextSnapshot | None:
        return self._last_snapshot

    def warn(self, message: str, *, path: str | None = None) -> None:
        """Attach a developer warning to the current Python capability evaluation."""
        self._warnings.append(f"[{path}] {message}" if path else message)

    def define_observation(self, spec: TelemetryFieldSpec) -> None:
        """Declare one canonical telemetry path and its validation contract."""
        self._telemetry_schema.define(spec)

    def observe(
        self,
        path_or_observation: str | TelemetryObservation,
        value: JSONValue | object = _UNSET,
        *,
        observed_at: datetime | None = None,
        received_at: datetime | None = None,
        source: str | None = None,
        ttl_ms: int | None = None,
    ) -> TelemetryObservation | None:
        """Store one observation, or read one for backward compatibility.

        Invalid evidence is stored with validation_errors so capability
        evaluation can return UNKNOWN instead of misclassifying it as a
        physical failure.
        """
        if isinstance(path_or_observation, TelemetryObservation):
            if value is not _UNSET:
                raise TypeError("value must not be supplied with TelemetryObservation")
            observation = path_or_observation
            validation_errors = list(observation.validation_errors)
            validation_errors.extend(
                f"{issue.code}: {issue.message}"
                for issue in self._telemetry_schema.validate(
                    observation.path, observation.value
                )
            )
            if validation_errors:
                observation.validation_errors = tuple(
                    dict.fromkeys(validation_errors)
                )
            spec = self._telemetry_schema.get(observation.path)
            if observation.ttl_ms is None and spec is not None:
                observation.ttl_ms = spec.ttl_ms
        else:
            if value is _UNSET:
                return self.get_observation(path_or_observation)

            now = datetime.now(timezone.utc)
            raw_value = value
            validation_errors: list[str] = []

            if not is_json_value(raw_value):
                validation_errors.append(
                    f"INVALID_JSON_VALUE: {type(raw_value).__name__}"
                )
                normalized_value: JSONValue = None
            else:
                normalized_value = cast(JSONValue, raw_value)

            validation_errors.extend(
                f"{issue.code}: {issue.message}"
                for issue in self._telemetry_schema.validate(
                    path_or_observation,
                    normalized_value,
                )
            )

            spec = self._telemetry_schema.get(path_or_observation)
            effective_ttl = ttl_ms if ttl_ms is not None else (
                spec.ttl_ms if spec is not None else None
            )

            observation = TelemetryObservation(
                path=path_or_observation,
                value=normalized_value,
                observed_at=observed_at or now,
                received_at=received_at or now,
                source=source,
                ttl_ms=effective_ttl,
                validation_errors=tuple(validation_errors),
            )

        self._store.set(observation)
        return observation

    def ingest(
        self,
        payload: Mapping[str, Any] | Any,
        *,
        normalizer: TelemetryNormalizer,
        observed_at: datetime | None = None,
        received_at: datetime | None = None,
        source: str | None = None,
    ) -> NormalizationResult:
        """Normalize a raw payload and store every resulting observation."""
        result = normalizer.normalize(
            payload,
            observed_at=observed_at,
            received_at=received_at,
            source=source,
        )
        for observation in result.observations:
            self.observe(observation)
        return result

    def get_observation(self, path: str) -> TelemetryObservation | None:
        """Return the current observation at a path."""
        return self._store.get(path)

    def define_capability(self, spec: CapabilitySpec) -> None:
        """Register or replace a capability definition."""
        if not spec.name:
            raise ValueError("CapabilitySpec.name must be non-empty")
        self._capabilities[spec.name] = spec

    def evaluate(self, name: str) -> CapabilityResult:
        """Evaluate a capability against current observations."""
        if name not in self._capabilities:
            raise UnknownCapabilityError(
                name,
                available_ids=tuple(self._capabilities),
            )

        self._warnings.clear()
        spec = self._capabilities[name]
        blocking: list[ConstraintResult] = []
        warnings: list[ConstraintResult] = []
        unknown_paths: list[str] = []

        for constraint in spec.requires:
            outcome = constraint.evaluate(self._store)
            if not outcome.passed:
                unknown_paths.extend(outcome.unknown_paths)
                blocking.append(
                    ConstraintResult.from_outcome(
                        outcome,
                        severity="blocking",
                    )
                )

        if spec.fn is not None:
            evaluator_error: Exception | None = None
            try:
                function_passed = bool(spec.fn(self))
            except Exception as exc:
                logger.exception("Capability function %s raised", name)
                self._warnings.append(str(exc))
                function_passed = False
                evaluator_error = exc

            if evaluator_error is not None:
                blocking.append(
                    ConstraintResult(
                        code="EVALUATOR_ERROR",
                        severity="blocking",
                        path="",
                        expected="capability evaluator completes successfully",
                        observed=None,
                        constraint_name=spec.name,
                        is_invalid=True,
                    )
                )
            elif not function_passed:
                blocking.append(
                    ConstraintResult(
                        code="PYTHON_FUNCTION",
                        severity="blocking",
                        path="",
                        expected="capability function returns True",
                        observed=False,
                        constraint_name=spec.name,
                    )
                )

        for constraint in spec.degrade_when:
            outcome = constraint.evaluate(self._store)
            if outcome.passed:
                warnings.append(
                    ConstraintResult.from_outcome(
                        outcome,
                        severity="warning",
                    )
                )

        if blocking:
            status = (
                CapabilityStatus.UNKNOWN
                if any(item.is_unknown for item in blocking)
                else CapabilityStatus.UNAVAILABLE
            )
        elif warnings:
            status = CapabilityStatus.DEGRADED
        else:
            status = CapabilityStatus.AVAILABLE

        result = CapabilityResult(
            name=name,
            status=status,
            blocking=blocking,
            warnings=warnings,
            unknown_paths=list(dict.fromkeys(unknown_paths)),
            python_warnings=list(self._warnings),
        )

        self._publish_capability_evaluated(name, result)
        previous = self._last_result.get(name)
        if previous is None or previous.status != result.status:
            transition = ContextTransition(
                capability=name,
                previous=previous.status if previous else None,
                current=result.status,
                reasons=[reason.to_dict() for reason in result.reasons],
            )
            self._transitions.append(transition)
            self._fire_transition_handlers(transition)
            self._publish_transition_detected(transition)

        self._last_result[name] = result
        logger.info("Capability %s -> %s", name, result.status.value)
        return result

    def evaluate_all(self) -> dict[str, CapabilityResult]:
        """Evaluate all registered capabilities."""
        return {name: self.evaluate(name) for name in self._capabilities}

    def snapshot(self) -> ContextSnapshot:
        """Return a fresh point-in-time machine context snapshot."""
        results = self.evaluate_all()
        snapshot = ContextSnapshot(
            schema_version="1.0",
            machine_ref=self._machine_ref,
            peaq_did=self._peaq_did,
            generated_at=datetime.now(timezone.utc),
            observations=self._store.all(),
            capabilities={
                name: CapabilitySnapshot.from_result(result)
                for name, result in results.items()
            },
            trace_id=self._trace_id,
        )
        self._last_snapshot = snapshot
        self._publish_snapshot_created(snapshot)
        return snapshot

    def on_transition(
        self, capability: str
    ) -> Callable[[TransitionCallback], TransitionCallback]:
        """Register a callback for state changes of one capability."""

        def decorator(callback: TransitionCallback) -> TransitionCallback:
            self._transition_handlers.setdefault(capability, []).append(callback)
            return callback

        return decorator

    def last_transition(
        self, capability: str | None = None
    ) -> ContextTransition | None:
        """Return the latest transition, optionally filtered by capability."""
        for transition in reversed(self._transitions):
            if capability is None or transition.capability == capability:
                return transition
        return None

    def transitions(self, capability: str | None = None) -> list[ContextTransition]:
        """Return recorded transitions, optionally filtered by capability."""
        if capability is None:
            return list(self._transitions)
        return [
            transition
            for transition in self._transitions
            if transition.capability == capability
        ]

    def _fire_transition_handlers(self, transition: ContextTransition) -> None:
        for handler in self._transition_handlers.get(transition.capability, []):
            try:
                handler(transition)
            except Exception:
                logger.exception(
                    "Transition handler failed for %s", transition.capability
                )

    def _publish_capability_evaluated(
        self, name: str, result: CapabilityResult
    ) -> None:
        if self._event_bus is None:
            return
        from sense_ai.events import CapabilityEvaluatedEvent

        self._event_bus._publish(
            CapabilityEvaluatedEvent(
                machine_id=self._machine_ref or "",
                capability_name=name,
                result=result,
            )
        )

    def _publish_transition_detected(self, transition: ContextTransition) -> None:
        if self._event_bus is None:
            return
        from sense_ai.events import TransitionDetectedEvent

        self._event_bus._publish(
            TransitionDetectedEvent(
                machine_id=self._machine_ref or "",
                transition=transition,
            )
        )

    def _publish_snapshot_created(self, snapshot: ContextSnapshot) -> None:
        if self._event_bus is None:
            return
        from sense_ai.events import SnapshotCreatedEvent

        self._event_bus._publish(
            SnapshotCreatedEvent(
                machine_id=self._machine_ref or "",
                snapshot_dict=snapshot.to_dict(),
            )
        )
