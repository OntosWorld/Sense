"""
capability() decorator and CapabilitySpec — per PRD §9.3 / §11.1.

Example (PRD §11.1)::

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
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sense_ai.rules import Constraint

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CapabilitySpec:
    """
    Frozen description of a machine capability and its evaluation rules.

    Parameters
    ----------
    name : str
        Unique capability identifier, e.g. ``"warehouse.pick"``.
    requires : Sequence[Constraint]
        Blocking constraints — all must pass for the capability to be
        ``AVAILABLE``.  A failure here produces ``UNAVAILABLE``.
    degrade_when : Sequence[Constraint], optional
        Warning constraints — a failure here produces ``DEGRADED`` but does
        not make the capability unavailable.
    version : str, optional
        Semantic version of this capability's specification.
    description : str, optional
        Human-readable description.
    inputs : dict[str, Any], optional
        Named inputs this capability accepts.
    outputs : dict[str, Any], optional
        Named outputs this capability produces.
    metadata : dict[str, Any], optional
        Provider-specific metadata.
    fn : callable, optional
        Python callable for programmatic capabilities (FR-5).
    """

    name: str
    requires: list[Constraint] = field(default_factory=list)
    degrade_when: list[Constraint] = field(default_factory=list)
    version: str = "1.0.0"
    description: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    fn: Callable[..., bool] | None = field(default=None)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("name must be non-empty")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _make(
    name: str,
    fn: Callable[..., bool] | None = None,
    *,
    requires: Sequence[Constraint] | None = None,
    degrade_when: Sequence[Constraint] | None = None,
    version: str = "1.0.0",
    description: str = "",
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> CapabilitySpec:
    """Create a CapabilitySpec from arguments."""
    return CapabilitySpec(
        name=name,
        requires=list(requires) if requires else [],
        degrade_when=list(degrade_when) if degrade_when else [],
        version=version,
        description=description,
        inputs=dict(inputs) if inputs else {},
        outputs=dict(outputs) if outputs else {},
        metadata=dict(metadata) if metadata else {},
        fn=fn,
    )


# ---------------------------------------------------------------------------
# capability() decorator — supports three call patterns
# ---------------------------------------------------------------------------
# 1. capability("foo", requires=[...])           → CapabilitySpec
# 2. @capability("foo", requires=[...])           → decorator → CapabilitySpec
# 3. @capability                                  → CapabilitySpec (fn wrapped)
#
# Implementation: always returns a callable.  When no kwargs are supplied
# (bare @capability) the callable is a CapabilitySpec that happens to implement
# __call__ so Python does not TypeError.  When kwargs are supplied, the
# callable is a 1-arg decorator function.
# ---------------------------------------------------------------------------


class _BareDecorator:
    """Returned by ``capability(fn)`` — a CapabilitySpec that is also callable."""

    __slots__ = ("_spec",)

    def __init__(self, spec: CapabilitySpec) -> None:
        object.__setattr__(self, "_spec", spec)

    def __call__(self, fn: Callable[..., bool]) -> CapabilitySpec:
        # Invariant: fn is passed but we return the original spec (name-only use)
        return self._spec  # type: ignore[no-any-return]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._spec, name)


def capability(  # noqa: A001  ('capability' is the intended public name)
    name_or_fn: str | Callable[..., bool] = "",
    *,
    name: str = "",
    requires: Sequence[Constraint] | None = None,
    degrade_when: Sequence[Constraint] | None = None,
    version: str = "1.0.0",
    description: str = "",
    inputs: dict[str, Any] | None = None,
    outputs: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> CapabilitySpec | _BareDecorator:
    """
    Define a named machine capability with evaluation constraints.

    Supports three call patterns:

    1. **As a plain function** (PRD §11.1 usage)::

           machine.define_capability(
               capability("warehouse.pick", requires=[...])
           )

    2. **As a decorator with arguments**::

           @capability("warehouse.pick", requires=[...])
           def my_capability(m: ContextMachine) -> bool:
               return m.observations["battery.level_pct"].value >= 20

    3. **As a bare decorator**::

           @capability
           def my_capability(m: ContextMachine) -> bool:
               return m.observations["battery.level_pct"].value >= 20

    Parameters
    ----------
    name_or_fn : str | callable
        Unique capability identifier, or a Python callable (bare ``@capability``).
    requires : Sequence[Constraint], optional
        Blocking constraints evaluated with ``severity="blocking"``.
    degrade_when : Sequence[Constraint], optional
        Warning constraints; failures produce ``DEGRADED``.
    version, description, inputs, outputs, metadata
        As per :class:`CapabilitySpec`.

    Returns
    -------
    CapabilitySpec | callable
        When called with a ``name`` argument, returns a ``CapabilitySpec``
        (or a decorator if used as ``@capability(name=...)``).
        When called as ``@capability`` with no args, returns a
        ``CapabilitySpec`` that is also callable.
    """

    # Resolve the name: prefer the explicit `name` kwarg, fall back to
    # `name_or_fn` (allows both `capability("foo")` and `capability(name="foo")`).
    effective_name = name or (name_or_fn if isinstance(name_or_fn, str) else "")

    # Detect bare ``@capability`` — name_or_fn is the decorated function itself.
    if callable(name_or_fn) and not isinstance(name_or_fn, str):
        fn = name_or_fn
        resolved_name = getattr(fn, "__name__", "anonymous")
        return _BareDecorator(_make(resolved_name, fn=fn))

    # No optional args → return a CapabilitySpec directly (not a decorator).
    if not any(
        [
            requires,
            degrade_when,
            inputs,
            outputs,
            metadata,
            description != "",
            version != "1.0.0",
        ]
    ):
        return _make(effective_name, requires=None, degrade_when=None)

    # With args, return a one-argument decorator only for
    # @capability(name=...) form. A positional string creates a spec directly.
    def decorator(fn: Callable[..., bool]) -> CapabilitySpec:
        return _make(
            effective_name,
            fn,
            requires=requires,
            degrade_when=degrade_when,
            version=version,
            description=description,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata,
        )

    # Decorator form: @capability(name="foo", ...)  →  return decorator
    # Non-decorator form: capability("foo", requires=[...])  →  return CapabilitySpec
    # Distinguish by checking whether an explicit `name` keyword was provided.
    # When `name` is non-empty → decorator mode (return decorator function).
    # When `name` is empty and name_or_fn is non-empty → non-decorator mode
    #   (capability("foo", requires=[...]) → CapabilitySpec directly).
    if name != "":
        # Decorator mode: return the decorator function itself (receives fn next).
        return decorator  # type: ignore[return-value]

    logger.debug("CapabilitySpec created: %s", effective_name)
    return _make(
        effective_name,
        requires=requires,
        degrade_when=degrade_when,
        version=version,
        description=description,
        inputs=inputs,
        outputs=outputs,
        metadata=metadata,
    )
