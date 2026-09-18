"""peaq Activity Event publisher for Sense capability transitions.

The adapter delegates signing, hashing, validation, and transaction submission to
peaq's official Python SDK. Sense never handles private keys.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from sense_ai import ContextSnapshot, ContextTransition
from sense_ai.errors import (
    PeaqConfigurationError,
    PeaqNetworkError,
    UnsupportedPeaqFlowError,
)


class PeaqEventClient(Protocol):
    """Minimal official peaqOS client surface used by Sense."""

    def submit_event(
        self,
        *,
        machine_id: int,
        event_type: int,
        value: int,
        timestamp: int,
        raw_data: bytes | None,
        trust_level: int,
        source_chain_id: int,
        source_tx_hash: Any,
        metadata: bytes,
        currency: str | None = None,
    ) -> tuple[str, bytes]: ...


@dataclass(frozen=True, slots=True)
class EventProvenance:
    """Evidence provenance attached to a peaq Activity Event."""

    trust_level: int = 0
    source_chain_id: int = 0
    source_tx_hash: str | bytes | None = None

    def __post_init__(self) -> None:
        if self.trust_level == 0:
            if self.source_chain_id != 0 or self.source_tx_hash is not None:
                raise PeaqConfigurationError(
                    "self-reported off-chain events must use source_chain_id=0 "
                    "and source_tx_hash=None"
                )
            return

        if self.trust_level == 1:
            if self.source_chain_id not in (3338, 8453):
                raise PeaqConfigurationError(
                    "on-chain verifiable events require source_chain_id 3338 "
                    "(peaq) or 8453 (Base)"
                )
            if self.source_tx_hash in (None, "", b""):
                raise PeaqConfigurationError(
                    "trust level 1 requires source_tx_hash"
                )
            return

        if self.trust_level == 2:
            raise UnsupportedPeaqFlowError(
                "Sense does not currently assert hardware-signed peaq events. "
                "Use trust level 0, or level 1 with an on-chain source proof."
            )

        raise PeaqConfigurationError("trust_level must be 0, 1, or 2")

    @classmethod
    def self_reported(cls) -> "EventProvenance":
        return cls()

    @classmethod
    def onchain(
        cls,
        *,
        source_chain_id: int,
        source_tx_hash: str | bytes,
    ) -> "EventProvenance":
        return cls(
            trust_level=1,
            source_chain_id=source_chain_id,
            source_tx_hash=source_tx_hash,
        )


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Result returned after peaq accepts an Activity Event."""

    tx_hash: str
    data_hash: bytes

    @property
    def data_hash_hex(self) -> str:
        return "0x" + self.data_hash.hex()


class PeaqEventPublisher:
    """Publish selected Sense transitions as peaq Activity Events."""

    def __init__(
        self,
        client: PeaqEventClient,
        machine_id: int,
        *,
        default_provenance: EventProvenance | None = None,
    ) -> None:
        if machine_id <= 0:
            raise PeaqConfigurationError("machine_id must be a positive integer")

        self._client = client
        self._machine_id = machine_id
        self._default_provenance = (
            default_provenance or EventProvenance.self_reported()
        )

    @property
    def machine_id(self) -> int:
        return self._machine_id

    @property
    def default_provenance(self) -> EventProvenance:
        return self._default_provenance

    def publish_transition(
        self,
        transition: ContextTransition,
        *,
        snapshot: ContextSnapshot | None = None,
        value: int = 0,
        metadata: dict[str, Any] | None = None,
        include_observed_values: bool = False,
        provenance: EventProvenance | None = None,
    ) -> PublishResult:
        """Submit one capability transition as a peaq Activity Event."""
        if value < 0:
            raise PeaqConfigurationError("activity event value must be non-negative")

        try:
            from peaq_os_sdk.constants import EVENT_TYPE_ACTIVITY
        except ImportError as exc:
            raise PeaqConfigurationError(
                "peaq-os-sdk is required; install sense-peaq or peaq-os-sdk"
            ) from exc

        selected_provenance = provenance or self._default_provenance
        raw_data = _encode_transition(
            transition,
            snapshot,
            include_observed_values=include_observed_values,
        )
        event_metadata = _encode_metadata(
            {
                "producer": "Sense",
                "kind": "capability_transition",
                "schema_version": snapshot.schema_version if snapshot else "1.0",
                **(metadata or {}),
            }
        )

        try:
            tx_hash, data_hash = self._client.submit_event(
                machine_id=self._machine_id,
                event_type=EVENT_TYPE_ACTIVITY,
                value=value,
                currency="",
                timestamp=max(1, int(transition.at.timestamp())),
                raw_data=raw_data,
                trust_level=selected_provenance.trust_level,
                source_chain_id=selected_provenance.source_chain_id,
                source_tx_hash=selected_provenance.source_tx_hash,
                metadata=event_metadata,
            )
        except Exception as exc:
            raise PeaqNetworkError(
                f"peaq Activity Event submission failed: {exc}",
                is_retryable=_looks_retryable(exc),
            ) from exc

        return PublishResult(tx_hash=str(tx_hash), data_hash=bytes(data_hash))


def _encode_transition(
    transition: ContextTransition,
    snapshot: ContextSnapshot | None,
    *,
    include_observed_values: bool,
) -> bytes:
    payload: dict[str, Any] = {
        "type": "sense.capability_transition",
        "transition": transition.to_dict(
            include_observed_values=include_observed_values
        ),
    }
    if snapshot is not None:
        capability = snapshot.capabilities.get(transition.capability)
        payload["machine_ref"] = snapshot.machine_ref
        payload["schema_version"] = snapshot.schema_version
        if capability is not None:
            payload["capability"] = {
                transition.capability: capability.to_dict(),
            }

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _encode_metadata(metadata: dict[str, Any]) -> bytes:
    encoded = json.dumps(
        metadata,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > 4096:
        raise PeaqConfigurationError("peaq event metadata exceeds 4096 bytes")
    return encoded


def _looks_retryable(exc: Exception) -> bool:
    text = str(exc).lower()
    permanent = (
        "validation",
        "invalid",
        "unauthorized",
        "forbidden",
        "revert",
        "insufficient",
    )
    return not any(token in text for token in permanent)


PeaqContextPublisher = PeaqEventPublisher
