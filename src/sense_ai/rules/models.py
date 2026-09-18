"""Rule data models."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..model import Situation

logger = logging.getLogger(__name__)

# Re-export for public API surface
__all__ = ["Rule", "RuleSet", "RuleResult"]


@dataclass
class RuleResult:
    """Outcome of evaluating a single rule against a situation."""

    rule_id: str
    passed: bool
    score: float  # 0.0 = failed, 1.0 = fully satisfied
    reason: str = ""
    metadata: dict = field(default_factory=dict)


class Rule:
    """
    A single, named evaluation rule.

    Parameters
    ----------
    rule_id : str
        Unique identifier for this rule.
    description : str
        Human-readable description of what this rule evaluates.
    weight : float
        Relative importance (0.0–1.0) of this rule in the aggregate score.
    evaluate : callable[[Situation], RuleResult]
        The evaluation function. Receives the situation and returns a result.
    """

    def __init__(
        self,
        rule_id: str,
        description: str,
        weight: float = 1.0,
        evaluate: object = None,
    ) -> None:
        self.rule_id = rule_id
        self.description = description
        self.weight = weight
        self._evaluate = evaluate

    def apply(self, situation: Situation) -> RuleResult:
        """Evaluate this rule against the given situation."""
        if self._evaluate is not None:
            result = self._evaluate(situation)
            logger.debug(
                "Rule %r evaluated: passed=%s score=%.2f",
                self.rule_id,
                result.passed,
                result.score,
            )
            return result
        # Default no-op rule
        return RuleResult(rule_id=self.rule_id, passed=True, score=1.0)


class RuleSet:
    """
    A named collection of rules applied together.

    Parameters
    ----------
    name : str
        Identifier for this rule set (e.g., "vision_quality", "safety").
    rules : list[Rule]
        Ordered list of rules in this set.
    """

    def __init__(self, name: str, rules: list[Rule] | None = None) -> None:
        self.name = name
        self.rules: list[Rule] = rules or []
        logger.debug("RuleSet created: name=%r rule_count=%d", name, len(self.rules))

    def add(self, rule: Rule) -> None:
        """Append a rule to this rule set."""
        logger.debug(
            "RuleSet %r: added rule %r (weight=%.2f)",
            self.name,
            rule.rule_id,
            rule.weight,
        )
        self.rules.append(rule)
