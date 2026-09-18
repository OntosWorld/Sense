"""peaq Activity Event publisher for Sense capability transitions.

The adapter delegates signing, hashing, validation, and transaction submission to
peaq's official Python SDK. Sense never handles private keys.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from sense_ai import ContextSnapshot, ContextTransition
from sense_ai.errors import PeaqConfigurationError, PeaqNetworkError


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
class PublishResult:
    """Result returned after peaq accepts an Activity Event."""

    tx_hash: str
    data_hash: bytes

    @property
    def data_hash_hex(self) -> str:
        return "0x" + self.data_hash.hex()


class PeaqEventPublisher:
    """Publish selected Sense transitions as peaq Activity Events.

    The client should be a configured peaq_os_sdk.PeaqosClient. Sense does not
    create or own the client's signing key.

    Local or off-chain machine context defaults to trust level 0 and source
    chain 0. Higher trust levels must only be used when the event genuinely
    satisfies peaq's documented provenance requirements.
    """

    def __init__(
        self,
        client: PeaqEventClient,
        machine_id: int,
        *,
        trust_level: int = 0,
        source_chain_id: int = 0,
    ) -> None:
        if machine_id <= 0:
            raise PeaqConfigurationError("machine_id must be a positive integer")
        if trust_level not in (0, 1, 2):
            raise PeaqConfigurationError("trust_level must be 0, 1, or 2")
        if source_chain_id not in (0, 3338, 8453):
            raise PeaqConfigurationError(
                "source_chain_id must be 0, 3338 (peaq), or 8453 (Base)"
            )

        self._client = client
        self._machine_id = machine_id
        self._trust_level = trust_level
        self._source_chain_id = source_chain_id

    @property
    def machine_id(self) -> int:
        return self._machine_id

    def publish_transition(
        self,
        transition: ContextTransition,
        *,
        snapshot: ContextSnapshot | None = None,
        value: int = 0,
        metadata: dict[str, Any] | None = None,
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

        raw_data = _encode_transition(transition, snapshot)
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
                trust_level=self._trust_level,
                source_chain_id=self._source_chain_id,
                source_tx_hash=None,
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
) -> bytes:
    payload: dict[str, Any] = {
        "type": "sense.capability_transition",
        "transition": transition.to_dict(),
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
