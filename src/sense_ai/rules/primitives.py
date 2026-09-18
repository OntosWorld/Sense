"""
Redundant compatibility shim — actual primitives are in __init__.py.

This file exists to satisfy any old import paths that referenced the
module directly.
"""

from . import (  # noqa: F401
    ALL,
    ANY,
    NONE_OF,
    NOT,
    ONLY_ONE,
    Constraint,
    ConstraintOutcome,
    Equals,
    Exists,
    Fresh,
    Gt,
    Gte,
    In,
    Lt,
    Lte,
    ObservationStore,
    equals,
    exists,
    fresh,
    gt,
    gte,
    lt,
    lte,
)
