"""Trust subsystem: deterministic trustworthiness evaluation and reporting (FR-12/FR-13)."""

from __future__ import annotations

from .engine import TrustDimension, TrustReport, compute_trust_report

__all__ = ["TrustDimension", "TrustReport", "compute_trust_report"]
