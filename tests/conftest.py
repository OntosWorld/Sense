"""Root conftest — installed by all test directories via pytest --rootdir."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable without installing the package
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Also make sense_peaq available when running e2e tests (not installed as a dep)
peaq_src = ROOT / "packages" / "Sense-peaq" / "src"
if peaq_src.exists():
    sys.path.insert(0, str(peaq_src))
