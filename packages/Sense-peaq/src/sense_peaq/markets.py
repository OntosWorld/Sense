"""Sense helpers for peaq Machine Markets / Scale.

This module does not implement a parallel marketplace API. All network
operations delegate to the official PeaqosClient.orchestration namespace.
"""

from __future__ import annotations

from typing import Any, Protocol

from sense_ai import CapabilityStatus, ContextSnapshot
from sense_ai.errors import PeaqConfigurationError, PeaqNetworkError


class _OrchestrationClient(Protocol):
    @property
    def orchestration(self) -> Any: ...


def to_market_context(snapshot: ContextSnapshot) -> dict[str, Any]:
    """Convert a Sense snapshot into runtime context suitable for agents.

    The returned object is intentionally transport-neutral. It can be embedded
    in an agent's task/request context without inventing unsupported peaq
    Machine Markets fields.
    """
    capabilities: dict[str, Any] = {}
    for name, capability in snapshot.capabilities.items():
        capabilities[name] = {
            "status": capability.status.value,
            "unknown_paths": list(capability.unknown_paths),
            "reasons": [*capability.blocking, *capability.warnings],
        }

    usable = [
        name
        for name, capability in snapshot.capabilities.items()
        if capability.status in (CapabilityStatus.AVAILABLE, CapabilityStatus.DEGRADED)
    ]

    return {
        "sense": {
            "schema_version": snapshot.schema_version,
            "generated_at": snapshot.generated_at.isoformat(),
            "machine_ref": snapshot.machine_ref,
            "capabilities": capabilities,
            "currently_usable_capabilities": usable,
        }
    }


class MachineMarketsAdapter:
    """Thin adapter over peaq's official orchestration client."""

    def __init__(self, peaq_client: _OrchestrationClient) -> None:
        self._client = peaq_client
        try:
            orchestration = peaq_client.orchestration
        except Exception as exc:
            raise PeaqConfigurationError(
                "peaq orchestration is not configured. Set "
                "PEAQOS_ORCHESTRATION_URL before creating PeaqosClient."
            ) from exc
        if orchestration is None:
            raise PeaqConfigurationError(
                "peaq orchestration is not configured. Set "
                "PEAQOS_ORCHESTRATION_URL before creating PeaqosClient."
            )
        self._orchestration = orchestration

    def list_machines(
        self,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Any:
        """Delegate to client.orchestration.list_machines()."""
        try:
            return self._orchestration.list_machines(limit=limit, cursor=cursor)
        except Exception as exc:
            raise _network_error("list machines", exc) from exc

    def list_market_services(
        self,
        options: Any = None,
        *,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> Any:
        """Delegate to client.orchestration.list_market_services()."""
        try:
            return self._orchestration.list_market_services(
                options,
                limit=limit,
                cursor=cursor,
            )
        except Exception as exc:
            raise _network_error("list market services", exc) from exc

    def search_market(self, params: Any, pairing_token: str) -> Any:
        """Delegate to client.orchestration.search_market().

        Construct params with the request types exported by peaq-os-sdk rather
        than a Sense-specific request model.
        """
        if not pairing_token:
            raise PeaqConfigurationError("pairing_token is required for market search")
        try:
            return self._orchestration.search_market(params, pairing_token)
        except Exception as exc:
            raise _network_error("search market", exc) from exc

    def get_market_search(self, search_id: str) -> Any:
        """Delegate to client.orchestration.get_market_search()."""
        if not search_id:
            raise PeaqConfigurationError("search_id must be non-empty")
        try:
            return self._orchestration.get_market_search(search_id)
        except Exception as exc:
            raise _network_error("get market search", exc) from exc


def _network_error(operation: str, exc: Exception) -> PeaqNetworkError:
    text = str(exc).lower()
    retryable = not any(
        token in text
        for token in (
            "validation",
            "auth",
            "forbidden",
            "not found",
            "not configured",
        )
    )
    return PeaqNetworkError(
        f"peaq orchestration failed to {operation}: {exc}",
        is_retryable=retryable,
    )
