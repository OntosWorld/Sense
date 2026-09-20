"""Official peaqOS integration for Sense."""

from __future__ import annotations

from .markets import (
    MachineMarketsAdapter,
    MarketEligibility,
    check_market_eligibility,
    filter_market_candidates,
    to_market_context,
)
from .network import (
    AGUNG,
    AGUNG_DEPLOYMENT_SOURCE,
    AGUNG_TOKENOMICS_SOURCE,
    PeaqNetworkProfile,
    apply_official_network_defaults,
    detect_network_profile,
)
from .publisher import (
    EventProvenance,
    PeaqContextPublisher,
    PeaqEventPublisher,
    PublishResult,
)

__all__ = [
    "AGUNG",
    "AGUNG_DEPLOYMENT_SOURCE",
    "AGUNG_TOKENOMICS_SOURCE",
    "EventProvenance",
    "MachineMarketsAdapter",
    "MarketEligibility",
    "PeaqContextPublisher",
    "PeaqEventPublisher",
    "PublishResult",
    "PeaqNetworkProfile",
    "apply_official_network_defaults",
    "check_market_eligibility",
    "detect_network_profile",
    "filter_market_candidates",
    "to_market_context",
]

__version__ = "0.3.0"
