"""Verified public peaqOS network configuration.

Contract addresses are public deployment metadata, not credentials. The Agung
profile below is sourced from peaq's official ``peaq-evm-smart-contracts``
repository and was verified against EVM chain ID 9990 on 2026-09-20.
"""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from dataclasses import dataclass

AGUNG_DEPLOYMENT_SOURCE = (
    "https://github.com/peaqnetwork/peaq-evm-smart-contracts/"
    "blob/dev/addresses/peaqos.json"
)
AGUNG_TOKENOMICS_SOURCE = "peaq-os-sdk:agung-2026-08-28 InfoDesk machine-data registry"


@dataclass(frozen=True, slots=True)
class PeaqNetworkProfile:
    """Public, non-secret configuration for one peaq network."""

    name: str
    chain_id: int
    tokenomics_deployment_id: str
    rpc_markers: tuple[str, ...]
    environment: dict[str, str]


AGUNG = PeaqNetworkProfile(
    name="agung",
    chain_id=9990,
    tokenomics_deployment_id="agung-2026-08-28",
    rpc_markers=("agung",),
    environment={
        "IDENTITY_REGISTRY_ADDRESS": "0x9E9463a65c7B74623b3b6Cdc39F71be7274e5971",
        "IDENTITY_STAKING_ADDRESS": "0x55f336714aDb0749DbFE33b057a1702405564E3d",
        # Tokenomics EventRegistry registered by the SDK-approved Agung
        # InfoDesk. The public peaqos.json still lists the legacy registry.
        "EVENT_REGISTRY_ADDRESS": "0x98De5e22c46e17A56235C3589586375B09F7c53D",
        "MACHINE_NFT_ADDRESS": "0xB41C2A4f1c19b6B06beaAce0F5CD8439e77C4b1c",
        "DID_REGISTRY_ADDRESS": "0x0000000000000000000000000000000000000800",
        "BATCH_PRECOMPILE_ADDRESS": "0x0000000000000000000000000000000000000805",
    },
)


def detect_network_profile(
    environ: MutableMapping[str, str] | None = None,
) -> PeaqNetworkProfile | None:
    """Detect a supported profile without guessing from unrelated settings."""
    values = environ if environ is not None else os.environ
    deployment_id = values.get("TOKENOMICS_DEPLOYMENT_ID", "").strip()
    if deployment_id == AGUNG.tokenomics_deployment_id:
        return AGUNG

    rpc_url = values.get("PEAQOS_RPC_URL", "").lower()
    if any(marker in rpc_url for marker in AGUNG.rpc_markers):
        return AGUNG
    return None


def apply_official_network_defaults(
    environ: MutableMapping[str, str] | None = None,
) -> PeaqNetworkProfile | None:
    """Apply verified public defaults while preserving every explicit value."""
    values = environ if environ is not None else os.environ
    profile = detect_network_profile(values)
    if profile is None:
        return None

    values.setdefault("TOKENOMICS_DEPLOYMENT_ID", profile.tokenomics_deployment_id)
    for key, value in profile.environment.items():
        values.setdefault(key, value)
    return profile
