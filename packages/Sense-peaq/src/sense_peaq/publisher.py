"""Official peaqOS Activity Event publishing for Sense context."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sense_ai import ContextSnapshot, ContextTransition
from sense_ai.errors import PeaqConfigurationError, PeaqNetworkError


@dataclass(frozen=True, slots=True)
class PublishResult:
    """Result returned after peaq accepts a Sense Activity Event."""

    tx_hash: str
    data_hash_hex: str


class PeaqContextPublisher:
    """
    Publish selected Sense context to peaq as Activity Events.

    Sense remains local-first. The caller chooses which transition or snapshot
    is published. By default snapshot publication uses publishable_view(), which
    excludes raw observations.

    Parameters
    ----------
    client:
        Configured official peaq_os_sdk.PeaqosClient instance.
    machine_id:
        peaq machine ID used by EventRegistry.
    trust_level:
        peaq event trust level. Defaults to TRUST_SELF_REPORTED. Sense does not
        upgrade this value automatically.
    source_chain_id:
        Source chain for the event. Defaults to peaq.
    """

    def __init__(
        self,
        client: Any,
        machine_id: int,
        *,
        trust_level: int | None = None,
        source_chain_id: int | None = None,
    ) -> None:
        if machine_id < 0:
            raise PeaqConfigurationError("machine_id must be a non-negative integer")

        try:
            from peaq_os_sdk import SUPPORTED_CHAINS, TRUST_SELF_REPORTED
        except ImportError as exc:
            raise PeaqConfigurationError(
                "peaq-os-sdk is required. Install sense-peaq or peaq-os-sdk>=0.8.0."
            ) from exc

        self._client = client
        self._machine_id = machine_id
        self._trust_level = (
            TRUST_SELF_REPORTED if trust_level is None else trust_level
        )
        self._source_chain_id = (
            SUPPORTED_CHAINS["peaq"] if source_chain_id is None else source_chain_id
        )

    @classmethod
    def from_env(cls, machine_id: int, **kwargs: Any) -> PeaqContextPublisher:
        """Build the publisher from the official PeaqosClient.from_env() config."""
        try:
            from peaq_os_sdk import PeaqosClient
        except ImportError as exc:
            raise PeaqConfigurationError(
                "peaq-os-sdk is required. Install sense-peaq or peaq-os-sdk>=0.8.0."
            ) from exc
        return cls(PeaqosClient.from_env(), machine_id, **kwargs)

    def publish_transition(
        self,
        transition: ContextTransition,
        *,
        machine_ref: str | None = None,
        schema_version: str = "1.0",
        include_observed_values: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> PublishResult:
        """Publish one meaningful capability state transition as an Activity Event."""
        payload = {
            "event": "sense.capability.transition",
            "schema_version": schema_version,
            "machine_ref": machine_ref,
            "transition": transition.to_dict(
                include_observed_values=include_observed_values
            ),
        }
        return self._submit_activity(
            payload=payload,
            timestamp=transition.at,
            metadata=metadata,
        )

    def publish_snapshot(
        self,
        snapshot: ContextSnapshot,
        *,
        include_observations: bool = False,
        observation_allowlist: tuple[str, ...] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PublishResult:
        """
        Publish a context snapshot as an Activity Event.

        Raw observations are excluded by default. If include_observations=True,
        an explicit observation_allowlist is required to avoid accidental
        telemetry disclosure.
        """
        if include_observations:
            if not observation_allowlist:
                raise PeaqConfigurationError(
                    "observation_allowlist is required when include_observations=True"
                )
            public_snapshot = snapshot.publishable_view(
                keep_observations=observation_allowlist
            )
        else:
            public_snapshot = snapshot.publishable_view()

        payload = {
            "event": "sense.context.snapshot",
            "schema_version": snapshot.schema_version,
            "context": public_snapshot.to_dict(),
        }
        return self._submit_activity(
            payload=payload,
            timestamp=snapshot.generated_at,
            metadata=metadata,
        )

    def publish(self, snapshot: ContextSnapshot) -> PublishResult:
        """Backward-compatible alias for privacy-preserving snapshot publishing."""
        return self.publish_snapshot(snapshot)

    def _submit_activity(
        self,
        *,
        payload: dict[str, Any],
        timestamp: datetime,
        metadata: dict[str, Any] | None,
    ) -> PublishResult:
        try:
            from peaq_os_sdk import EVENT_TYPE_ACTIVITY
        except ImportError as exc:
            raise PeaqConfigurationError(
                "peaq-os-sdk is required. Install sense-peaq or peaq-os-sdk>=0.8.0."
            ) from exc

        raw_data = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        metadata_bytes = json.dumps(
            {
                "producer": "sense-ai",
                "schema": payload.get("schema_version", "1.0"),
                **(metadata or {}),
            },
            separators=(",", ":"),
            sort_keys=True,
            default=str,
        ).encode("utf-8")

        try:
            tx_hash, data_hash = self._client.submit_event(
                machine_id=self._machine_id,
                event_type=EVENT_TYPE_ACTIVITY,
                value=0,
                currency="",
                timestamp=int(timestamp.timestamp()),
                raw_data=raw_data,
                trust_level=self._trust_level,
                source_chain_id=self._source_chain_id,
                source_tx_hash=None,
                metadata=metadata_bytes,
            )
        except Exception as exc:
            raise PeaqNetworkError(
                f"peaq Activity Event submission failed: {exc}",
                is_retryable=False,
                transaction_id=None,
            ) from exc

        return PublishResult(
            tx_hash=str(tx_hash),
            data_hash_hex=bytes(data_hash).hex(),
        )
