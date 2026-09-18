"""Pytest shared fixtures and configuration."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow importing src.Sense without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
