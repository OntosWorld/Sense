"""
Machine Markets adapter for peaq.

Machine Markets is peaq's on-chain registry where machine operators advertise
capability listings and consumers discover/query them.

This module provides:
- ``MachineListing`` – a machine's on-chain capability advertisement.
- ``MachineMarketsAdapter`` – query listings, register new ones, and update them.

PRD reference: §8 (peaq integration).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Sequence

from sense_ai import (
    CapabilityStatus,
    ContextSnapshot,
)

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Domain types
# ----------------------------------------------------------------------


class ListingState(Enum):
    """Lifecycle state of a Machine Markets listing."""

    ACTIVE = "active"
    """Available for discovery and bidding."""

    SUSPENDED = "suspended"
    """Temporarily withdrawn; can be reactivated."""

    RETIRED = "retired"
    """Permanently removed from the market."""


@dataclass(frozen=True)
class ListingConstraints:
    """Constraints attached to a listing (price, SLA, region, etc.)."""

    price_per_call_usd: float | None = None
    """Price per capability evaluation call in USD."""

    min_uptime_percent: float | None = None
    """Minimum required uptime percentage."""

    region_codes: tuple[str, ...] = ()
    """ISO 3166-1 alpha-2 region codes this machine serves."""

    custom: dict[str, Any] = field(default_factory=dict)
    """Arbitrary additional key-value constraints."""


@dataclass(frozen=True)
class MachineListing:
    """
    A machine's on-chain Machine Markets listing.

    Corresponds to the ``ContextSnapshot`` capability set plus market-specific
    metadata.
    """

    listing_id: str
    """On-chain listing identifier (assigned by peaq on registration)."""

    machine_id: str
    """Sense machine identifier."""

    owner_did: str
    """peaq DID of the machine owner."""

    capability_names: tuple[str, ...]
    """Names of capabilities exposed by this listing."""

    state: ListingState = ListingState.ACTIVE

    constraints: ListingConstraints = field(default_factory=ListingConstraints)

    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Resolved from on-chain data
    latest_status_overall: CapabilityStatus | None = None
    """Computed overall status across all capabilities (AVAILABLE = best)."""

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_id": self.listing_id,
            "machine_id": self.machine_id,
            "owner_did": self.owner_did,
            "capability_names": list(self.capability_names),
            "state": self.state.value,
            "constraints": {
                "price_per_call_usd": self.constraints.price_per_call_usd,
                "min_uptime_percent": self.constraints.min_uptime_percent,
                "region_codes": list(self.constraints.region_codes),
                "custom": self.constraints.custom,
            },
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "latest_status_overall": (
                self.latest_status_overall.value
                if self.latest_status_overall is not None
                else None
            ),
        }

    @classmethod
    def from_snapshot(
        cls,
        snap: ContextSnapshot,
        owner_did: str,
        constraints: ListingConstraints | None = None,
    ) -> MachineListing:
        """Build a ``MachineListing`` from a ``ContextSnapshot``."""
        cap_names = tuple(snap.capabilities.keys())
        statuses = [cs.status for cs in snap.capabilities.values()]

        # Overall = best non-UNKNOWN status (UNKNOWN means insufficient data)
        priority = {
            CapabilityStatus.AVAILABLE: 0,
            CapabilityStatus.DEGRADED: 1,
            CapabilityStatus.UNKNOWN: 2,
            CapabilityStatus.UNAVAILABLE: 3,
        }
        best = min(statuses, key=lambda s: priority.get(s, 99)) if statuses else None

        return cls(
            listing_id="",  # assigned by peaq on registration
            machine_id=snap.machine_ref,
            owner_did=owner_did,
            capability_names=cap_names,
            constraints=constraints or ListingConstraints(),
            latest_status_overall=best,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MachineListing:
        """Parse a ``MachineListing`` from a Machine Markets API response dict."""
        from sense_ai import CapabilityStatus

        raw_constraints = data.get("constraints", {})
        state_str = data.get("state", "active")

        # Parse latest_status_overall
        status_str = data.get("latest_status_overall")
        latest_status: CapabilityStatus | None = None
        if status_str:
            try:
                latest_status = CapabilityStatus(status_str.upper())
            except ValueError:
                latest_status = None

        return cls(
            listing_id=str(data.get("listing_id", "")),
            machine_id=str(data.get("machine_id", "")),
            owner_did=str(data.get("owner_did", "")),
            capability_names=tuple(data.get("capability_names", [])),
            state=ListingState(state_str)
            if state_str in {s.value for s in ListingState}
            else ListingState.ACTIVE,
            constraints=ListingConstraints(
                price_per_call_usd=raw_constraints.get("price_per_call_usd"),
                min_uptime_percent=raw_constraints.get("min_uptime_percent"),
                region_codes=tuple(raw_constraints.get("region_codes", [])),
                custom=raw_constraints.get("custom", {}),
            ),
            registered_at=cls._parse_datetime(data.get("registered_at")),
            updated_at=cls._parse_datetime(data.get("updated_at")),
            latest_status_overall=latest_status,
        )

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)


def to_market_context(
    snapshot: ContextSnapshot,
    owner_did: str,
    constraints: ListingConstraints | None = None,
) -> MachineListing:
    """Convenience: build a ``MachineListing`` from a ``ContextSnapshot``.

    This is a one-liner equivalent to::

        MachineListing.from_snapshot(snapshot, owner_did, constraints)

    FR-11 – exposes the snapshot→listing conversion as a top-level helper so callers
    do not need to import ``MachineListing`` directly.

    Args:
        snapshot:  A ``ContextSnapshot`` from the Sense evaluation engine.
        owner_did: The machine operator's peaq DID (e.g. ``"did:peaq:0x..."``).
        constraints: Optional pricing / uptime / region constraints for the listing.

    Returns:
        A ``MachineListing`` ready for submission via ``MachineMarketsAdapter``.
    """
    return MachineListing.from_snapshot(snapshot, owner_did, constraints)


# ----------------------------------------------------------------------
# Exceptions
# ----------------------------------------------------------------------


class MarketsError(Exception):
    """Base exception for Machine Markets operations."""


class ListingNotFoundError(MarketsError):
    """Raised when a listing cannot be found on-chain."""


class ListingConflictError(MarketsError):
    """Raised when a listing already exists and overwrite is not permitted."""


# ----------------------------------------------------------------------
# MachineMarketsAdapter
# ----------------------------------------------------------------------

_DEFAULT_API = "https://peaq.network/api/v1/machine-markets"


class MachineMarketsAdapter:
    """
    Client for the peaq Machine Markets API.

    Provides:
    - ``register`` – publish a new capability listing on-chain.
    - ``update`` – refresh a listing with a new snapshot.
    - ``query`` – search for listings by capability, region, or status.
    - ``deactivate`` / ``reactivate`` – change listing state.

    Usage::

        from sense_ai import ContextMachine
        from sense_peaq import MachineMarketsAdapter, ListingConstraints

        adapter = MachineMarketsAdapter(api_key="pk_live_...")

        # Register
        listing = adapter.register(
            snapshot=machine.snapshot(),
            owner_did="did:peaq:machine-001",
            constraints=ListingConstraints(price_per_call_usd=0.001),
        )
        print(f"Listed as {listing.listing_id}")

        # Later: refresh with updated snapshot
        updated = adapter.update(listing.listing_id, machine.snapshot())
    """

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = _DEFAULT_API,
        _http_client: Callable[..., Any] | None = None,
    ) -> None:
        self._api_key = api_key
        self._api_url = api_url.rstrip("/")
        self._client = _http_client

    # ------------------------------------------------------------------
    # Public API (PRD §8)
    # ------------------------------------------------------------------

    def register(
        self,
        snapshot: ContextSnapshot,
        owner_did: str,
        constraints: ListingConstraints | None = None,
        listing_id_hint: str | None = None,
    ) -> MachineListing:
        """
        Register a new machine capability listing on Machine Markets.

        Args:
            snapshot: The machine's current ``ContextSnapshot``.
            owner_did: The peaq DID of the listing owner (must control the signing key).
            constraints: Optional market constraints (price, SLA, region).
            listing_id_hint: Optional. If provided and a listing with this ID already
                exists, acts as an update instead of a new registration.

        Returns:
            The registered ``MachineListing`` with its assigned ``listing_id``.

        Raises:
            ListingConflictError: a listing already exists for this machine and
                ``listing_id_hint`` was not provided to disambiguate.
            MarketsError: the API call failed.
        """
        listing = MachineListing.from_snapshot(snapshot, owner_did, constraints)

        payload: dict[str, Any] = {
            "owner_did": owner_did,
            "machine_id": snapshot.machine_ref,
            "capabilities": {
                name: cs.to_dict() for name, cs in snapshot.capabilities.items()
            },
            "constraints": listing.to_dict()["constraints"],
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }

        if listing_id_hint:
            return MachineListing.from_dict(
                self._rpc("PATCH", f"/listings/{listing_id_hint}", payload)
            )

        try:
            return MachineListing.from_dict(self._rpc("POST", "/listings", payload))
        except MarketsError as exc:
            if "already exists" in str(exc).lower():
                raise ListingConflictError(
                    f"A listing already exists for machine {snapshot.machine_ref}. "
                    "Pass listing_id_hint to update it instead."
                ) from exc
            raise

    def update(
        self,
        listing_id: str,
        snapshot: ContextSnapshot,
    ) -> MachineListing:
        """
        Refresh ``listing_id`` with the latest ``snapshot`` and current status.

        Raises:
            ListingNotFoundError: no listing with the given ID exists.
        """
        listing = self._fetch(listing_id)
        updated = MachineListing.from_snapshot(
            snapshot,
            owner_did=listing.owner_did,
            constraints=listing.constraints,
        )
        # Preserve the on-chain ID and registration time
        object.__setattr__(updated, "listing_id", listing_id)
        object.__setattr__(updated, "registered_at", listing.registered_at)
        object.__setattr__(updated, "updated_at", datetime.now(timezone.utc))

        payload: dict[str, Any] = {
            "capabilities": {
                name: cs.to_dict() for name, cs in snapshot.capabilities.items()
            },
            "latest_status_overall": (
                updated.latest_status_overall.value
                if updated.latest_status_overall is not None
                else None
            ),
            "updated_at": updated.updated_at.isoformat(),
        }
        return MachineListing.from_dict(
            self._rpc("PATCH", f"/listings/{listing_id}", payload)
        )

    def query(
        self,
        capability: str | None = None,
        region_codes: Sequence[str] | None = None,
        min_uptime_percent: float | None = None,
        status_required: CapabilityStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[MachineListing]:
        """
        Search Machine Markets for listings matching the given criteria.

        All filters are AND-combined.
        """
        params: dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }
        if capability:
            params["capability"] = capability
        if region_codes:
            params["region_codes"] = ",".join(region_codes)
        if min_uptime_percent is not None:
            params["min_uptime_percent"] = min_uptime_percent
        if status_required is not None:
            params["status"] = status_required.value

        return [
            MachineListing.from_dict(item)
            for item in self._rpc("GET", "/listings/search", params=params)
        ]

    def get(self, listing_id: str) -> MachineListing:
        """Fetch a single listing by its on-chain ID."""
        return self._fetch(listing_id)

    def deactivate(self, listing_id: str) -> MachineListing:
        """Temporarily suspend a listing."""
        return MachineListing.from_dict(
            self._rpc("POST", f"/listings/{listing_id}/suspend", {})
        )

    def reactivate(self, listing_id: str) -> MachineListing:
        """Reactivate a previously suspended listing."""
        return MachineListing.from_dict(
            self._rpc("POST", f"/listings/{listing_id}/reactivate", {})
        )

    # ------------------------------------------------------------------
    # Internal HTTP dispatch
    # ------------------------------------------------------------------

    def _fetch(self, listing_id: str) -> MachineListing:
        try:
            return MachineListing.from_dict(self._rpc("GET", f"/listings/{listing_id}"))
        except MarketsError as exc:
            raise ListingNotFoundError(f"Listing {listing_id!r} not found") from exc

    def _rpc(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:

        if self._client is not None:
            client = self._client
        else:
            try:
                import httpx as _httpx  # type: ignore[import-not-found]
            except ImportError as exc:
                raise MarketsError(
                    "httpx is required for Machine Markets. "
                    "Install with: pip install sense-ai[peaq]"
                ) from exc
            client = _httpx.Client(
                base_url=self._api_url,
                headers={"Authorization": f"Bearer {self._api_key}"}
                if self._api_key
                else {},
                timeout=30.0,
            )

        url = f"{self._api_url}{path}"
        try:
            if method == "GET":
                resp = client.get(url, params=params or {})
            elif method == "POST":
                resp = client.post(url, json=payload or {})
            elif method == "PATCH":
                resp = client.patch(url, json=payload or {})
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if resp.status_code == 404:
                raise ListingNotFoundError(f"Resource not found: {path}")
            if resp.status_code >= 400:
                raise MarketsError(
                    f"Machine Markets API error {resp.status_code}: {resp.text}"
                )
            return resp.json()
        finally:
            getattr(client, "close", lambda: None)()
