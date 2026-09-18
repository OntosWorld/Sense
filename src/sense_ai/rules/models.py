"""Legacy generic rule data models.

The primary Sense capability engine lives in :mod:`sense_ai.rules`. These
small helpers remain for compatibility with older callers that use generic
callable rules.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["Rule", "RuleResult", "RuleSet"]


@dataclass(slots=True)
class RuleResult:
    """Outcome of evaluating one generic compatibility rule."""

    rule_id: str
    passed: bool
    score: float
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


RuleEvaluator = Callable[[Any], RuleResult]


class Rule:
    """A named compatibility rule backed by a callable evaluator."""

    def __init__(
        self,
        rule_id: str,
        description: str,
        weight: float = 1.0,
        evaluate: RuleEvaluator | None = None,
    ) -> None:
        self.rule_id = rule_id
        self.description = description
        self.weight = weight
        self._evaluate = evaluate

    def apply(self, situation: Any) -> RuleResult:
        """Evaluate this rule against a caller-defined situation object."""
        if self._evaluate is None:
            return RuleResult(rule_id=self.rule_id, passed=True, score=1.0)

        result = self._evaluate(situation)
        logger.debug(
            "Rule %r evaluated: passed=%s score=%.2f",
            self.rule_id,
            result.passed,
            result.score,
        )
        return result


class RuleSet:
    """A named collection of compatibility rules."""

    def __init__(self, name: str, rules: list[Rule] | None = None) -> None:
        self.name = name
        self.rules = list(rules or [])

    def add(self, rule: Rule) -> None:
        """Append a rule to this rule set."""
        self.rules.append(rule)
