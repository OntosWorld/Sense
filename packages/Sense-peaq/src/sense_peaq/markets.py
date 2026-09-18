"""Thin adapter over peaqOS Machine Markets orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sense_ai import CapabilityStatus, ContextSnapshot
from sense_ai.errors import PeaqConfigurationError, PeaqNetworkError


@dataclass(frozen=True, slots=True)
class SenseMarketContext:
    """
    Sense-derived runtime context that an application can use alongside peaq
    Machine Markets results.

    This is not an on-chain peaq listing schema and is never submitted
    automatically.
    """

    machine_ref: str | None
    generated_at: str
    capabilities: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "machine_ref": self.machine_ref,
            "generated_at": self.generated_at,
            "capabilities": dict(self.capabilities),
        }


def to_market_context(snapshot: ContextSnapshot) -> SenseMarketContext:
    """
    Convert a Sense snapshot to runtime capability context.

    peaq Machine Markets owns the marketplace/service schema. Sense contributes
    live physical capability state; callers decide how to use it when searching,
    filtering, ordering, or executing market services.
    """
    return SenseMarketContext(
        machine_ref=snapshot.machine_ref,
        generated_at=snapshot.generated_at.isoformat(),
        capabilities={
            name: cap.status.value for name, cap in snapshot.capabilities.items()
        },
    )


class MachineMarketsAdapter:
    """
    Thin wrapper around the official peaq_os_sdk client.orchestration namespace.

    The adapter deliberately does not invent listing, bidding, or registry
    endpoints. Every network operation delegates to a documented peaqOS SDK
    method.
    """

    def __init__(self, client: Any) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> MachineMarketsAdapter:
        try:
            from peaq_os_sdk import PeaqosClient
        except ImportError as exc:
            raise PeaqConfigurationError(
                "peaq-os-sdk is required. Install sense-peaq or peaq-os-sdk>=0.8.0."
            ) from exc
        return cls(PeaqosClient.from_env())

    @property
    def orchestration(self) -> Any:
        try:
            return self._client.orchestration
        except Exception as exc:
            raise PeaqConfigurationError(
                "peaq orchestration is not configured. Set PEAQOS_ORCHESTRATION_URL "
                "or pass orchestration_url to PeaqosClient."
            ) from exc

    def list_machines(
        self, *, limit: int | None = None, cursor: str | None = None
    ) -> Any:
        try:
            return self.orchestration.list_machines(limit=limit, cursor=cursor)
        except Exception as exc:
            raise self._network_error("list_machines", exc) from exc

    def list_market_services(
        self,
        options: Any | None = None,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Any:
        try:
            return self.orchestration.list_market_services(
                options,
                limit=limit,
                cursor=cursor,
            )
        except Exception as exc:
            raise self._network_error("list_market_services", exc) from exc

    def get_market_service(
        self,
        service_id: str,
        options: Any | None = None,
    ) -> Any:
        try:
            return self.orchestration.get_market_service(service_id, options)
        except Exception as exc:
            raise self._network_error("get_market_service", exc) from exc

    def search_market(self, params: Any, pairing_token: str) -> Any:
        try:
            return self.orchestration.search_market(params, pairing_token)
        except Exception as exc:
            raise self._network_error("search_market", exc) from exc

    @staticmethod
    def currently_usable_capabilities(
        snapshot: ContextSnapshot,
        *,
        include_degraded: bool = True,
    ) -> tuple[str, ...]:
        """
        Return capability names Sense currently considers usable.

        This helper is local-only; it does not mutate peaq machine capabilities.
        """
        usable = {CapabilityStatus.AVAILABLE}
        if include_degraded:
            usable.add(CapabilityStatus.DEGRADED)
        return tuple(
            name
            for name, capability in snapshot.capabilities.items()
            if capability.status in usable
        )

    @staticmethod
    def _network_error(operation: str, exc: Exception) -> PeaqNetworkError:
        return PeaqNetworkError(
            f"peaq orchestration {operation} failed: {exc}",
            is_retryable=False,
            transaction_id=None,
        )
