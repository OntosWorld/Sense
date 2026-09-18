"""Sense helpers for peaq Machine Markets / Scale.

Network operations delegate to the official PeaqosClient.orchestration
namespace. Runtime capability gating remains local and transport-neutral.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

from sense_ai import CapabilityStatus, ContextSnapshot
from sense_ai.errors import PeaqConfigurationError, PeaqNetworkError

T = TypeVar("T")


class _OrchestrationClient(Protocol):
    @property
    def orchestration(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class MarketEligibility:
    """Local Sense decision about whether a machine can satisfy a request."""

    eligible: bool
    required_capabilities: tuple[str, ...]
    accepted: tuple[str, ...]
    rejected: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "eligible": self.eligible,
            "required_capabilities": list(self.required_capabilities),
            "accepted": list(self.accepted),
            "rejected": dict(self.rejected),
        }


def check_market_eligibility(
    snapshot: ContextSnapshot,
    required_capabilities: Iterable[str],
    *,
    allow_degraded: bool = True,
) -> MarketEligibility:
    """Gate market selection using current Sense capability state."""
    required = tuple(dict.fromkeys(required_capabilities))
    accepted_statuses = {CapabilityStatus.AVAILABLE}
    if allow_degraded:
        accepted_statuses.add(CapabilityStatus.DEGRADED)

    accepted: list[str] = []
    rejected: dict[str, str] = {}

    for capability_name in required:
        capability = snapshot.capabilities.get(capability_name)
        if capability is None:
            rejected[capability_name] = "MISSING_CAPABILITY"
            continue
        if capability.status in accepted_statuses:
            accepted.append(capability_name)
        else:
            rejected[capability_name] = capability.status.value

    return MarketEligibility(
        eligible=not rejected,
        required_capabilities=required,
        accepted=tuple(accepted),
        rejected=rejected,
    )


def filter_market_candidates(
    candidates: Iterable[T],
    *,
    snapshots_by_machine: Mapping[str, ContextSnapshot],
    required_capabilities: Iterable[str],
    machine_ref: Callable[[T], str | None],
    allow_degraded: bool = True,
) -> list[T]:
    """Filter arbitrary peaq market results using caller-supplied machine refs.

    Sense deliberately does not guess fields on peaq SDK response types.
    The caller provides the machine_ref extractor for the current SDK model.
    """
    selected: list[T] = []
    for candidate in candidates:
        ref = machine_ref(candidate)
        if ref is None:
            continue
        snapshot = snapshots_by_machine.get(ref)
        if snapshot is None:
            continue
        if check_market_eligibility(
            snapshot,
            required_capabilities,
            allow_degraded=allow_degraded,
        ).eligible:
            selected.append(candidate)
    return selected


def to_market_context(snapshot: ContextSnapshot) -> dict[str, Any]:
    """Convert a Sense snapshot into runtime context suitable for agents."""
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
        try:
            return self._orchestration.list_market_services(
                options,
                limit=limit,
                cursor=cursor,
            )
        except Exception as exc:
            raise _network_error("list market services", exc) from exc

    def get_market_service(
        self,
        service_id: str,
        options: Any = None,
    ) -> Any:
        if not service_id:
            raise PeaqConfigurationError("service_id must be non-empty")
        try:
            return self._orchestration.get_market_service(service_id, options)
        except Exception as exc:
            raise _network_error("get market service", exc) from exc

    def search_market(self, params: Any, pairing_token: str) -> Any:
        if not pairing_token:
            raise PeaqConfigurationError("pairing_token is required for market search")
        try:
            return self._orchestration.search_market(params, pairing_token)
        except Exception as exc:
            raise _network_error("search market", exc) from exc

    def get_market_search(self, search_id: str) -> Any:
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
