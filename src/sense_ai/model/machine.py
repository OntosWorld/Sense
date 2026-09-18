"""
ContextMachine — the main SDK entry point, per PRD §8.1 / §11.1.

Usage (PRD §11.1)::

    from Sense import ContextMachine, capability
    from sense_ai.rules import equals, gte, fresh

    machine = ContextMachine(
        machine_ref="robot-001",
        peaq_did="did:peaq:..."
    )

    machine.define_capability(
        capability(
            "warehouse.pick",
            requires=[
                equals("tool.gripper.available", True),
                equals("safety.estop", False),
                gte("battery.level_pct", 20),
                fresh("localization.pose", max_age_ms=1000),
            ],
            degrade_when=[
                gte("payload.utilization_pct", 90)
            ]
        )
    )

    machine.observe("battery.level_pct", 34, observed_at=now)
    result = machine.evaluate("warehouse.pick")
    snapshot = machine.snapshot()
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from sense_ai.errors import UnknownCapabilityError
from sense_ai.model.capability import CapabilitySpec
from sense_ai.model.observation import JsonValue, TelemetryObservation
from sense_ai.model.result import (
    CapabilityResult,
    CapabilityStatus,
    ConstraintResult,
    ContextTransition,
)
from sense_ai.model.snapshot import CapabilitySnapshot, ContextSnapshot
from sense_ai.rules import ObservationStore

if TYPE_CHECKING:
    from sense_ai.events import EventBus

logger = logging.getLogger(__name__)

_UNSET = object()


# ---------------------------------------------------------------------------
# Internal dict-backed observation store
# ---------------------------------------------------------------------------


class _DictStore(ObservationStore):
    """In-memory ``ObservationStore`` backed by a dict of path → observation."""

    __slots__ = ("_obs",)

    def __init__(self) -> None:
        self._obs: dict[str, TelemetryObservation] = {}

    def set(self, obs: TelemetryObservation) -> None:
        self._obs[obs.path] = obs

    def get(self, path: str) -> TelemetryObservation | None:
        return self._obs.get(path)

    def all(self) -> dict[str, TelemetryObservation]:
        return dict(self._obs)

    def __repr__(self) -> str:
        return f"_DictStore({len(self._obs)} observations)"


# ---------------------------------------------------------------------------
# Transition callback type
# ---------------------------------------------------------------------------

TransitionCallback = Callable[[ContextTransition], None]


# ---------------------------------------------------------------------------
# ContextMachine
# ---------------------------------------------------------------------------


class ContextMachine:
    """
    Physical AI / robotics machine context engine.

    Ingest telemetry, define capability rules, evaluate current state, and
    produce serializable :class:`ContextSnapshot` objects.

    Parameters
    ----------
    machine_ref : str, optional
        Developer-supplied machine identifier (e.g. ``"robot-001"``).
    peaq_did : str, optional
        peaq decentralized identifier bound to this machine (PRD §8.1).
        Must be a valid ``did:peaq:...`` string if provided.
    trace_id : str, optional
        Distributed-trace identifier attached to all snapshots.
    """

    __slots__ = (
        "_machine_ref",
        "_peaq_did",
        "_trace_id",
        "_store",
        "_obs_count",
        "_capabilities",
        "_last_result",
        "_last_snapshot",
        "_last_snapshot_obs_count",
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
    ) -> None:
        self._machine_ref = machine_ref
        self._peaq_did = peaq_did
        self._trace_id = trace_id
        self._store: _DictStore = _DictStore()
        self._capabilities: dict[str, CapabilitySpec] = {}
        self._last_result: dict[str, CapabilityResult] = {}
        self._last_snapshot: ContextSnapshot | None = None
        self._transitions: list[ContextTransition] = []
        self._transition_handlers: dict[str, list[TransitionCallback]] = {}
        self._event_bus: EventBus | None = event_bus
        self._warnings: list[str] = []  # warnings emitted by Python capability fns
        self._obs_count = 0
        self._last_snapshot_obs_count: int | None = None

    # -------------------------------------------------------------------------
    # warn() — emit a warning from within a Python capability function
    # -------------------------------------------------------------------------

    def warn(self, message: str, *, path: str | None = None) -> None:
        """
        Emit a warning during capability evaluation.

        Warnings are collected and attached to the ``CapabilityResult`` returned
        by the enclosing ``evaluate()`` call.  They do not change the overall
        status unless the capability function returns ``False``.

        Parameters
        ----------
        message : str
            Human-readable warning text.
        path : str, optional
            Observation path this warning relates to (for diagnostics).
        """
        entry = f"[{path}] {message}" if path else message
        self._warnings.append(entry)

    # -------------------------------------------------------------------------
    # Public properties
    # -------------------------------------------------------------------------

    @property
    def machine_ref(self) -> str | None:
        return self._machine_ref

    @property
    def peaq_did(self) -> str | None:
        return self._peaq_did

    @property
    def observations(self) -> dict[str, TelemetryObservation]:
        """Current observation store as a dict (read-only copy)."""
        return self._store.all()

    @property
    def capability_names(self) -> tuple[str, ...]:
        """Names of all registered capabilities."""
        return tuple(self._capabilities.keys())

    # -------------------------------------------------------------------------
    # Telemetry ingestion (FR-1)
    # -------------------------------------------------------------------------

    def observe(
        self,
        path_or_obs: str | TelemetryObservation,
        value: JsonValue | object = _UNSET,
        *,
        observed_at: datetime | None = None,
        received_at: datetime | None = None,
        source: str | None = None,
        ttl_ms: int | None = None,
    ) -> TelemetryObservation | None:
        """
        Ingest a telemetry observation (FR-1, PRD §11.1).

        May be called with an existing :class:`TelemetryObservation` as the sole
        positional argument, or with the ``(path, value)`` signature.

        Parameters
        ----------
        path_or_obs : str | TelemetryObservation
            Dot-notation key, e.g. ``"battery.level_pct"``, or an existing
            observation object.
        value : float | str | bool
            The observed value (required when ``path_or_obs`` is a str).
        observed_at : datetime, optional
            When the value was observed.  Defaults to UTC now.
        source : str, optional
            Originating sensor or adapter identifier.
        ttl_ms : int, optional
            Source-provided validity hint in milliseconds.

        Returns
        -------
        TelemetryObservation
            The stored observation.

        Raises
        ------
        ValueError
            When ``path`` is empty.

        Example
        -------
        >>> from datetime import datetime, timezone
        >>> now = datetime.now(timezone.utc)
        >>> machine.observe("battery.level_pct", 34, observed_at=now, ttl_ms=5000)
        >>> machine.observe(some_telemetry_observation)
        """
        if isinstance(path_or_obs, TelemetryObservation):
            obs = path_or_obs
        elif value is _UNSET:
            return self.get_observation(path_or_obs)
        else:
            now = datetime.now(timezone.utc)
            obs = TelemetryObservation(
                path=path_or_obs,
                value=value,  # type: ignore[arg-type]
                observed_at=observed_at or now,
                received_at=received_at or now,
                source=source,
                ttl_ms=ttl_ms,
            )
        self._store.set(obs)
        self._obs_count += 1
        return obs

    def get_observation(self, path: str) -> TelemetryObservation | None:
        """Return the latest observation stored at path without mutating state."""
        return self._store.get(path)

    # -------------------------------------------------------------------------
    # Capability registration (FR-1 / §11.1)
    # -------------------------------------------------------------------------

    def define_capability(self, spec: CapabilitySpec) -> None:
        """
        Register a capability definition (FR-1, PRD §11.1).

        Capabilities are additive; registering the same name twice replaces
        the previous definition.

        Parameters
        ----------
        spec : CapabilitySpec
            The capability definition, typically created via :func:`capability()`.

        Raises
        ------
        ValueError
            If ``spec`` has no name.
        """
        if not spec.name:
            raise ValueError("CapabilitySpec.name must be non-empty")
        self._capabilities[spec.name] = spec
        logger.debug("Capability registered: %s", spec.name)

    # -------------------------------------------------------------------------
    # Evaluation (FR-5 / FR-6 / §9.4)
    # -------------------------------------------------------------------------

    def evaluate(self, name: str) -> CapabilityResult:
        """
        Evaluate a registered capability against current observations (FR-5, FR-6).

        Status logic (PRD §9.4):

        - **UNAVAILABLE**: at least one blocking constraint (``requires``) failed.
          Failures due to absent/stale data are still UNAVAILABLE for blocking
          constraints.
        - **UNKNOWN**: a blocking constraint's observation path is absent OR
          a ``Fresh`` constraint is violated (stale).  This means we cannot
          safely conclude the machine is unavailable — we simply don't know.
        - **DEGRADED**: all blocking constraints pass (or resolve to UNKNOWN
          without blocking), and at least one warning constraint
          (``degrade_when``) failed.
        - **AVAILABLE**: all blocking constraints pass, no warnings failed.

        Parameters
        ----------
        name : str
            Name of a previously registered capability.

        Returns
        -------
        CapabilityResult
            The evaluation result with status and per-constraint explanations.

        Raises
        ------
        KeyError
            If ``name`` has not been registered via :meth:`define_capability`.

        Example
        -------
        >>> result = machine.evaluate("warehouse.pick")
        >>> print(result.status)   # CapabilityStatus.AVAILABLE | DEGRADED | UNAVAILABLE | UNKNOWN
        """
        if name not in self._capabilities:
            raise UnknownCapabilityError(
                name,
                available_ids=tuple(self._capabilities.keys()),
            )

        self._warnings.clear()  # reset per-evaluation

        spec = self._capabilities[name]
        blocking: list[ConstraintResult] = []
        warnings: list[ConstraintResult] = []
        unknown_paths: list[str] = []

        # Evaluate blocking constraints (requires)
        for constraint in spec.requires:
            outcome = constraint.evaluate(self._store)

            if not outcome.passed:
                if outcome.is_absent or outcome.is_stale:
                    # Stale/missing data for a blocking constraint → UNKNOWN
                    unknown_paths.append(outcome.path)
                blocking.append(
                    ConstraintResult(
                        code=outcome.code,
                        severity="blocking",
                        path=outcome.path,
                        expected=outcome.expected,
                        observed=outcome.observed,
                        observed_age_ms=outcome.age_ms,
                        constraint_name=outcome.constraint_name,
                        is_absent=outcome.is_absent,
                        is_stale=outcome.is_stale,
                    )
                )

        # Python capability function: False = blocking failure
        if spec.fn is not None:
            try:
                fn_passed = spec.fn(self)
            except Exception as exc:
                self._warnings.append(str(exc))
                fn_passed = False
            if not fn_passed:
                blocking.append(
                    ConstraintResult(
                        code="PYTHON_FUNCTION",
                        severity="blocking",
                        path="",
                        expected="Python capability function returned True",
                        observed=f"Python capability function returned {fn_passed!r}",
                        observed_age_ms=0,
                        constraint_name=spec.name,
                        is_absent=False,
                        is_stale=False,
                    )
                )

        # Evaluate warning constraints (degrade_when)
        # A degrade_when constraint describes the BAD state; when it PASSES
        # (the bad state is present) the capability is degraded.
        for constraint in spec.degrade_when:
            outcome = constraint.evaluate(self._store)

            if outcome.passed:
                if outcome.is_absent or outcome.is_stale:
                    unknown_paths.append(outcome.path)
                warnings.append(
                    ConstraintResult(
                        code=outcome.code,
                        severity="warning",
                        path=outcome.path,
                        expected=outcome.expected,
                        observed=outcome.observed,
                        observed_age_ms=outcome.age_ms,
                        constraint_name=outcome.constraint_name,
                        is_absent=outcome.is_absent,
                        is_stale=outcome.is_stale,
                    )
                )

        # Determine overall status
        if blocking:
            # Some blocking constraints failed — check if any are UNKNOWN
            unknown_blocking = any(r.is_absent or r.is_stale for r in blocking)
            if unknown_blocking:
                # At least one blocking constraint is UNKNOWN
                status: CapabilityStatus = CapabilityStatus.UNKNOWN
            else:
                # All blocking failures are concrete → UNAVAILABLE
                status = CapabilityStatus.UNAVAILABLE
        elif warnings:
            # All blocking constraints pass; warnings exist → DEGRADED
            status = CapabilityStatus.DEGRADED
        else:
            status = CapabilityStatus.AVAILABLE

        # Merge Python-function warnings into the result
        python_warnings = list(self._warnings)

        result = CapabilityResult(
            name=name,
            status=status,
            blocking=blocking,
            warnings=warnings,
            unknown_paths=unknown_paths,
            python_warnings=python_warnings,
        )

        # Publish CapabilityEvaluatedEvent
        self._publish_capability_evaluated(name, result)

        # Detect transition
        previous = self._last_result.get(name)
        if previous is None or previous.status != status:
            transition = ContextTransition(
                capability=name,
                previous=previous.status if previous else None,
                current=status,
                reasons=[*blocking, *warnings],
            )
            self._transitions.append(transition)
            self._fire_transition_handlers(transition)
            self._publish_transition_detected(transition)

        self._last_result[name] = result
        logger.info("Capability %s → %s", name, result.status.value)
        return result

    def evaluate_all(self) -> dict[str, CapabilityResult]:
        """
        Evaluate all registered capabilities.

        Returns
        -------
        dict[str, CapabilityResult]
            Mapping of capability name → result.
        """
        return {name: self.evaluate(name) for name in self._capabilities}

    # -------------------------------------------------------------------------
    # Snapshot (FR-3 / §9.2 / §11.2)
    # -------------------------------------------------------------------------

    def snapshot(self) -> ContextSnapshot:
        """
        Produce a versioned point-in-time context snapshot (FR-3, PRD §11.2).

        This re-evaluates all capabilities to ensure the snapshot reflects
        current state.

        Returns
        -------
        ContextSnapshot
            Serializable snapshot of current machine context.

        Example
        -------
        >>> payload = machine.snapshot().to_dict()
        """
        # Re-evaluate on every snapshot request. Freshness changes as wall-clock
        # time passes even when no new telemetry arrives, so caching solely on
        # observation count can return a stale AVAILABLE result.
        results = self.evaluate_all()

        snap = ContextSnapshot(
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
        self._last_snapshot = snap
        self._publish_snapshot_created(snap)
        return snap

    @property
    def last_snapshot(self) -> ContextSnapshot | None:
        """The most recently produced snapshot, or ``None``."""
        return self._last_snapshot

    # -------------------------------------------------------------------------
    # Transition engine (FR-8)
    # -------------------------------------------------------------------------

    def on_transition(
        self, capability: str
    ) -> Callable[[TransitionCallback], TransitionCallback]:
        """
        Decorator to register a callback for a capability-state transition (FR-8).

        Parameters
        ----------
        capability : str
            Capability name to watch.

        Returns
        -------
        Callable
            Decorator that registers the callback.

        Example
        -------
        >>> @machine.on_transition("warehouse.pick")
        ... def handle(event: ContextTransition) -> None:
        ...     print(f"Transition: {event.label}")

        Note
        ----
        The decorator returns the callback unchanged so it can also be used
        standalone without affecting its behaviour.
        """

        def decorator(cb: TransitionCallback) -> TransitionCallback:
            if capability not in self._transition_handlers:
                self._transition_handlers[capability] = []
            self._transition_handlers[capability].append(cb)
            return cb

        return decorator

    def last_transition(
        self, capability: str | None = None
    ) -> ContextTransition | None:
        """Return the most recent transition, optionally filtered by capability."""
        for transition in reversed(self._transitions):
            if capability is None or transition.capability == capability:
                return transition
        return None

    def transitions(self, capability: str | None = None) -> list[ContextTransition]:
        """
        Return recorded transitions, optionally filtered by capability name.
        """
        if capability is None:
            return list(self._transitions)
        return [t for t in self._transitions if t.capability == capability]

    def _fire_transition_handlers(self, transition: ContextTransition) -> None:
        handlers = self._transition_handlers.get(transition.capability, [])
        for handler in handlers:
            try:
                handler(transition)
            except Exception:
                pass  # User callbacks must not raise

    # -------------------------------------------------------------------------
    # Event bus helpers
    # -------------------------------------------------------------------------

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
                result=result.to_dict(),
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

    def _publish_snapshot_created(self, snap: ContextSnapshot) -> None:
        if self._event_bus is None:
            return
        from sense_ai.events import SnapshotCreatedEvent

        self._event_bus._publish(
            SnapshotCreatedEvent(
                machine_id=self._machine_ref or "",
                snapshot_dict=snap.to_dict(),
            )
        )
