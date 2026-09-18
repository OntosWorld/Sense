"""
Deterministic rule engine — PRD §10 FR-5.

Every constraint is a pure function of the current observation store.
No hosted AI, no randomness.

Public API per PRD §11.1::

    from sense_ai.rules import equals, gte, fresh, ALL, ANY, NOT

Example (PRD §11.1)::

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
"""

from __future__ import annotations

import logging
import operator
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sense_ai.model.observation import TelemetryObservation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Observation store protocol
# ---------------------------------------------------------------------------


class ObservationStore(ABC):
    """
    Abstract view over a machine's current observation set.

    Concrete implementations (``_DictStore``) are internal; the public API
    never exposes this class directly.
    """

    @abstractmethod
    def get(self, path: str) -> TelemetryObservation | None:
        """Return the observation at ``path``, or ``None`` if absent."""
        ...

    @abstractmethod
    def all(self) -> dict[str, TelemetryObservation]:
        """Return a copy of all observations keyed by path."""
        ...


# ---------------------------------------------------------------------------
# Constraint result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConstraintOutcome:
    """
    Result of evaluating one :class:`Constraint` against an observation store.

    Attributes
    ----------
    passed : bool
        ``True`` when the constraint is satisfied.
    code : str
        Stable machine-readable identifier for this outcome.
    path : str
        The observation path this constraint evaluated.
    expected : str
        Human-readable description of what was expected.
    observed : Any
        The actual value from the store, or ``None``.
    age_ms : int | None
        Age of the observation at evaluation time in milliseconds.
        ``None`` when the path was absent.
    is_stale : bool
        ``True`` when ``age_ms > max_age_ms`` (only set for :class:`Fresh`).
    is_absent : bool
        ``True`` when no observation existed at ``path``.
    constraint_name : str | None
        Optional developer-supplied label for the rule.
    """

    passed: bool
    code: str
    path: str
    expected: str
    observed: Any
    age_ms: int | None = None
    is_stale: bool = False
    is_absent: bool = False
    constraint_name: str | None = None


# ---------------------------------------------------------------------------
# Base constraint
# ---------------------------------------------------------------------------


class Constraint(ABC):
    """
    Abstract base for all rule primitives.

    Each concrete constraint is immutable and evaluable against any
    ``ObservationStore``.
    """

    __slots__ = ("_path", "_name", "_severity")

    def __init__(
        self,
        path: str,
        *,
        name: str | None = None,
        severity: str = "blocking",
    ) -> None:
        if severity not in ("blocking", "warning"):
            raise ValueError('severity must be "blocking" or "warning"')
        self._path = path
        self._name = name
        self._severity = severity

    @property
    def path(self) -> str:
        return self._path

    @property
    def name(self) -> str | None:
        return self._name

    @property
    def severity(self) -> str:
        return self._severity

    @abstractmethod
    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        """Evaluate this constraint against ``store`` and return the outcome."""
        ...

    # Convenience so composition functions can treat all constraints uniformly.
    def __call__(self, store: ObservationStore) -> ConstraintOutcome:
        return self.evaluate(store)

    def _base_outcome(
        self,
        store: ObservationStore,
        *,
        passed: bool,
        code: str,
        expected: str,
        is_stale: bool = False,
    ) -> ConstraintOutcome:
        obs = store.get(self._path)
        return ConstraintOutcome(
            passed=passed,
            code=code,
            path=self._path,
            expected=expected,
            observed=obs.value if obs is not None else None,
            age_ms=obs.age_ms if obs is not None else None,
            is_stale=is_stale,
            is_absent=obs is None,
            constraint_name=self._name,
        )

    def _missing_outcome(self, store: ObservationStore, code: str) -> ConstraintOutcome:
        """Return a "not passed" outcome for an absent path."""
        return ConstraintOutcome(
            passed=False,
            code=code,
            path=self._path,
            expected="<observation present>",
            observed=None,
            age_ms=None,
            is_stale=False,
            is_absent=True,
            constraint_name=self._name,
        )

    def blocking(self) -> Constraint:
        """Return a copy of this constraint with ``severity="blocking"``."""
        if self._severity == "blocking":
            return self
        return self._replace(severity="blocking")

    def warning(self) -> Constraint:
        """Return a copy of this constraint with ``severity="warning"``."""
        if self._severity == "warning":
            return self
        return self._replace(severity="warning")

    def named(self, name: str) -> Constraint:
        """Return a copy of this constraint with a human-readable label."""
        return self._replace(name=name)

    def _replace(self, **kwargs: Any) -> Constraint:
        """Virtual clone-constructor for immutable dataclass-like attrs."""
        params = {"path": self._path, "name": self._name, "severity": self._severity}
        params.update(kwargs)
        return self.__class__(**params)  # type: ignore[arg-type]

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self._path!r} {self._name or ''}>"


# ---------------------------------------------------------------------------
# Primitive constraints
# ---------------------------------------------------------------------------


class Equals(Constraint):
    """
    Assert that an observation's value equals the expected value.

    Parameters
    ----------
    path : str
        Observation path.
    expected : Any
        Expected value.  Supports bool, int, float, str.
    name : str, optional
        Developer label.
    severity : str
        ``"blocking"`` (default) or ``"warning"``.
    """

    __slots__ = ("_expected",)

    def __init__(
        self,
        path: str,
        expected: Any,
        *,
        name: str | None = None,
        severity: str = "blocking",
    ) -> None:
        super().__init__(path, name=name, severity=severity)
        self._expected = expected
        logger.debug(
            "Equals constraint created: path=%r expected=%r severity=%s",
            path,
            expected,
            severity,
        )

    @property
    def expected_value(self) -> Any:
        return self._expected

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        obs = store.get(self._path)
        if obs is None:
            code = f"MISSING_{self._path.upper().replace('.', '_')}"
            return self._missing_outcome(store, code)

        passed = obs.value == self._expected
        code = (
            f"{'PASS' if passed else 'FAIL'}_EQ_{self._path.upper().replace('.', '_')}"
        )
        return self._base_outcome(
            store,
            passed=passed,
            code=code,
            expected=f"value == {self._expected!r}",
        )


class _ComparisonOp(Constraint):
    """Base for numeric comparison constraints."""

    __slots__ = ("_threshold", "_op")

    _OPS: dict[str, Callable[[Any, Any], bool]] = {
        "gte": operator.ge,
        "gt": operator.gt,
        "lte": operator.le,
        "lt": operator.lt,
    }

    def __init__(
        self,
        path: str,
        threshold: float,
        *,
        name: str | None = None,
        severity: str = "blocking",
    ) -> None:
        super().__init__(path, name=name, severity=severity)
        self._threshold = threshold
        self._op = self._OPS[self.__class__.__name__.lower()]
        logger.debug(
            "%s constraint created: path=%r threshold=%r severity=%s",
            self.__class__.__name__,
            path,
            threshold,
            severity,
        )

    @property
    def threshold(self) -> float:
        return self._threshold

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        obs = store.get(self._path)
        if obs is None:
            code = f"MISSING_{self._path.upper().replace('.', '_')}"
            return self._missing_outcome(store, code)

        # Only numeric values support comparison
        if not isinstance(obs.value, (int, float)):
            return self._base_outcome(
                store,
                passed=False,
                code=f"TYPE_ERROR_{self.__class__.__name__.upper()}",
                expected=f"numeric value {self._op.__name__} {self._threshold}",
            )

        passed = self._op(obs.value, self._threshold)
        op_name = self.__class__.__name__.upper()
        outcome = "PASS" if passed else "FAIL"
        path_code = self._path.upper().replace(".", "_")
        code = f"{outcome}_{op_name}_{path_code}"
        return self._base_outcome(
            store,
            passed=passed,
            code=code,
            expected=f"value {self._op.__name__} {self._threshold}",
        )


class Gte(_ComparisonOp):
    """Assert that a numeric observation is greater than or equal to a threshold."""

    __slots__ = ()


class Gt(_ComparisonOp):
    """Assert that a numeric observation is strictly greater than a threshold."""

    __slots__ = ()


class Lte(_ComparisonOp):
    """Assert that a numeric observation is less than or equal to a threshold."""

    __slots__ = ()


class Lt(_ComparisonOp):
    """Assert that a numeric observation is strictly less than a threshold."""

    __slots__ = ()


class Fresh(Constraint):
    """
    Assert that an observation is present and no older than ``max_age_ms``.

    If the observation is absent → ``passed=False`` with ``is_absent=True``.
    If the observation is present but too old → ``passed=False`` with
    ``is_stale=True``.  The caller uses ``is_absent`` vs ``is_stale`` to
    decide between ``UNKNOWN`` and ``UNAVAILABLE`` based on severity.

    Parameters
    ----------
    path : str
        Observation path.
    max_age_ms : int
        Maximum permitted age in milliseconds.
    name : str, optional
        Developer label.
    severity : str
        ``"blocking"`` (default) or ``"warning"``.
    """

    __slots__ = ("_max_age_ms",)

    def __init__(
        self,
        path: str,
        max_age_ms: int,
        *,
        name: str | None = None,
        severity: str = "blocking",
    ) -> None:
        super().__init__(path, name=name, severity=severity)
        if max_age_ms <= 0:
            raise ValueError("max_age_ms must be a positive integer")
        self._max_age_ms = max_age_ms
        logger.debug(
            "Fresh constraint created: path=%r max_age_ms=%d severity=%s",
            path,
            max_age_ms,
            severity,
        )

    @property
    def max_age_ms(self) -> int:
        return self._max_age_ms

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        obs = store.get(self._path)
        if obs is None:
            code = f"MISSING_{self._path.upper().replace('.', '_')}"
            return self._missing_outcome(store, code)

        age_ms = obs.age_ms
        is_stale = age_ms > self._max_age_ms
        passed = not is_stale
        outcome = "PASS" if passed else "FAIL"
        path_code = self._path.upper().replace(".", "_")
        code = f"{outcome}_FRESH_{path_code}"
        return self._base_outcome(
            store,
            passed=passed,
            code=code,
            expected=f"age <= {self._max_age_ms}ms",
            is_stale=is_stale,
        )


class In(Constraint):
    """
    Assert that an observation's value is a member of a set.

    Parameters
    ----------
    path : str
        Observation path.
    values : Sequence[Any]
        Permitted values.
    name : str, optional
        Developer label.
    severity : str
        ``"blocking"`` (default) or ``"warning"``.
    """

    __slots__ = ("_values",)

    def __init__(
        self,
        path: str,
        values: Sequence[Any],
        *,
        name: str | None = None,
        severity: str = "blocking",
    ) -> None:
        super().__init__(path, name=name, severity=severity)
        self._values = tuple(values)
        logger.debug(
            "In constraint created: path=%r values=%s severity=%s",
            path,
            self._values,
            severity,
        )

    @property
    def values(self) -> tuple[Any, ...]:
        return self._values

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        obs = store.get(self._path)
        if obs is None:
            code = f"MISSING_{self._path.upper().replace('.', '_')}"
            return self._missing_outcome(store, code)

        passed = obs.value in self._values
        code = (
            f"{'PASS' if passed else 'FAIL'}_IN_{self._path.upper().replace('.', '_')}"
        )
        return self._base_outcome(
            store,
            passed=passed,
            code=code,
            expected=f"value in {self._values!r}",
        )


class Exists(Constraint):
    """
    Assert that an observation path is present in the store.

    The value itself is not examined.

    Parameters
    ----------
    path : str
        Observation path that must exist.
    name : str, optional
        Developer label.
    severity : str
        ``"blocking"`` (default) or ``"warning"``.
    """

    __slots__ = ()

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        obs = store.get(self._path)
        if obs is None:
            code = f"MISSING_{self._path.upper().replace('.', '_')}"
            return self._missing_outcome(store, code)

        return self._base_outcome(
            store,
            passed=True,
            code=f"PASS_EXISTS_{self._path.upper().replace('.', '_')}",
            expected="<observation present>",
        )


# ---------------------------------------------------------------------------
# Composition operators
# ---------------------------------------------------------------------------


def NOT(constraint: Constraint) -> _Negated:
    """Logical negation of a single constraint."""
    return _Negated(constraint)


def ALL(*constraints: Constraint) -> _All:
    """All constraints must pass (AND)."""
    return _All(list(constraints))


def ANY(*constraints: Constraint) -> _Any:
    """At least one constraint must pass (OR)."""
    return _Any(list(constraints))


def NONE_OF(*constraints: Constraint) -> _NoneOf:
    """None of the constraints may pass (NOR)."""
    return _NoneOf(list(constraints))


def ONLY_ONE(*constraints: Constraint) -> _OnlyOne:
    """Exactly one constraint must pass (XOR)."""
    return _OnlyOne(list(constraints))


# Composed constraints delegate to inner Constraint.evaluate() where possible.
# The composed objects are themselves Constraint subclasses so the engine
# can call .evaluate() uniformly.


class _Negated(Constraint):
    __slots__ = ("_inner",)

    def __init__(self, inner: Constraint) -> None:
        super().__init__(inner.path, name=inner.name, severity=inner.severity)
        self._inner = inner

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        inner = self._inner.evaluate(store)
        return ConstraintOutcome(
            passed=not inner.passed,  # negated: passing inner means failing negated
            code=f"NOT_{inner.code}",
            path=self._path,
            expected=f"NOT ({inner.expected})",
            observed=inner.observed,
            age_ms=inner.age_ms,
            is_stale=inner.is_stale,
            is_absent=inner.is_absent,
            constraint_name=self._name,
        )


class _All(Constraint):
    __slots__ = ("_constraints",)

    def __init__(self, constraints: list[Constraint]) -> None:
        # Use the first constraint's path as the composition path (may be overridden)
        first = constraints[0] if constraints else None
        super().__init__(
            first.path if first else "",
            name=None,
            severity=first.severity if first else "blocking",
        )
        self._constraints = constraints

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        outcomes = [c.evaluate(store) for c in self._constraints]
        passed = all(o.passed for o in outcomes)
        code = f"{'PASS' if passed else 'FAIL'}_ALL"
        logger.debug(
            "ALL evaluated: %s (%d constraints, %d passed)",
            code,
            len(self._constraints),
            sum(1 for o in outcomes if o.passed),
        )
        return ConstraintOutcome(
            passed=passed,
            code=code,
            path=self._path,
            expected=f"ALL({len(self._constraints)} constraints)",
            observed=[o.observed for o in outcomes],
            age_ms=None,
            constraint_name=self._name,
        )


class _Any(Constraint):
    __slots__ = ("_constraints",)

    def __init__(self, constraints: list[Constraint]) -> None:
        first = constraints[0] if constraints else None
        super().__init__(
            first.path if first else "",
            name=None,
            severity=first.severity if first else "blocking",
        )
        self._constraints = constraints

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        outcomes = [c.evaluate(store) for c in self._constraints]
        passed = any(o.passed for o in outcomes)
        code = f"{'PASS' if passed else 'FAIL'}_ANY"
        logger.debug(
            "ANY evaluated: %s (%d constraints, %d passed)",
            code,
            len(self._constraints),
            sum(1 for o in outcomes if o.passed),
        )
        return ConstraintOutcome(
            passed=passed,
            code=code,
            path=self._path,
            expected=f"ANY({len(self._constraints)} constraints)",
            observed=[o.observed for o in outcomes],
            age_ms=None,
            constraint_name=self._name,
        )


class _NoneOf(Constraint):
    __slots__ = ("_constraints",)

    def __init__(self, constraints: list[Constraint]) -> None:
        first = constraints[0] if constraints else None
        super().__init__(
            first.path if first else "",
            name=None,
            severity=first.severity if first else "blocking",
        )
        self._constraints = constraints

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        outcomes = [c.evaluate(store) for c in self._constraints]
        passed = not any(o.passed for o in outcomes)
        code = f"{'PASS' if passed else 'FAIL'}_NONE_OF"
        return ConstraintOutcome(
            passed=passed,
            code=code,
            path=self._path,
            expected=f"NONE_OF({len(self._constraints)} constraints)",
            observed=[o.observed for o in outcomes],
            age_ms=None,
            constraint_name=self._name,
        )


class _OnlyOne(Constraint):
    __slots__ = ("_constraints",)

    def __init__(self, constraints: list[Constraint]) -> None:
        first = constraints[0] if constraints else None
        super().__init__(
            first.path if first else "",
            name=None,
            severity=first.severity if first else "blocking",
        )
        self._constraints = constraints

    def evaluate(self, store: ObservationStore) -> ConstraintOutcome:
        outcomes = [c.evaluate(store) for c in self._constraints]
        passed = sum(1 for o in outcomes if o.passed) == 1
        code = f"{'PASS' if passed else 'FAIL'}_ONLY_ONE"
        return ConstraintOutcome(
            passed=passed,
            code=code,
            path=self._path,
            expected=f"ONLY_ONE({len(self._constraints)} constraints)",
            observed=[o.observed for o in outcomes],
            age_ms=None,
            constraint_name=self._name,
        )


# ---------------------------------------------------------------------------
# Public convenience factories (PRD §11.1 surface)
# ---------------------------------------------------------------------------

equals = Equals
fresh = Fresh
in_ = In  # 'in' is a Python keyword; public alias is 'in_'
exists = Exists
gte = Gte
gt = Gt
lte = Lte
lt = Lt
