"""
Sense-peaq – peaq network integration for Sense.

Provides:
- ``PeaqContextPublisher`` – submits capability snapshots to peaq as signed DID documents.
- ``MachineMarketsAdapter`` – queries and bids on machine capability listings.
- ``to_market_context`` – convenience helper to convert a ContextSnapshot into a MachineListing.

Requires the ``peaqsdk`` package. Install with: ``pip install sense-ai[peaq]``
"""

from __future__ import annotations

from .markets import MachineMarketsAdapter, to_market_context
from .publisher import PeaqContextPublisher

__all__ = [
    "PeaqContextPublisher",
    "MachineMarketsAdapter",
    "to_market_context",
]
