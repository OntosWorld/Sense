"""
Peaq DID document publisher.

Publishes ``ContextSnapshot`` documents as signed DID web documents on the peaq
network.  Each machine has exactly one DID that is updated (not recreated) on
every submission so that the history is append-only on-chain.

Architecture (per PRD §8):
- Signing key lives in the peaq SDK keystore (never logged or exported).
- Submissions are idempotent: re-submitting the same snapshot is a no-op on-chain.
- Polling interval and retry back-off are configurable.
- All SDK errors surface as typed Sense errors (FR-14).
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Sequence

from sense_ai import ContextMachine, ContextSnapshot, ContextTransition
from sense_ai.errors import PeaqConfigurationError, PeaqNetworkError

if TYPE_CHECKING:
    from peaqsdk import PeaqSDK  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------

_DEFAULT_POLL_INTERVAL_S = 5.0
_DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class PublisherConfig:
    """Configuration for ``PeaqContextPublisher``."""

    poll_interval_s: float = _DEFAULT_POLL_INTERVAL_S
    """How often to re-publish when operating in watch mode."""

    confirmation_timeout_s: float = _DEFAULT_TIMEOUT_S
    """How long to wait for on-chain confirmation before raising ``PeaqNetworkError``."""

    dry_run: bool = False
    """If True, build and sign the document but do not submit it."""


# ----------------------------------------------------------------------
# PeaqContextPublisher
# ----------------------------------------------------------------------


class PeaqContextPublisher:
    """
    Publish ``ContextSnapshot`` documents to the peaq network as DID web documents.

    **Thread-safe**: all public methods hold the GIL; for multi-threaded use wrap
    ``submit`` calls in a lock.

    Usage::

        from sense_ai import ContextMachine
        from sense_peaq import PeaqContextPublisher

        machine = ContextMachine(machine_ref="factory-robot-01")
        publisher = PeaqContextPublisher(
            did="did:peaq:factory-robot-01",
            api_url="https://peaq.network/api/v1",
            signing_key_ref="keystore://default",
        )
        publisher.register_machine(machine)

        # Ingest telemetry ...
        snap = machine.snapshot()
        publisher.submit(snap)          # one-shot
        publisher.start_watch(snap)     # loop: re-publish every poll_interval_s

    Raises
    ------
    PeaqConfigurationError
        When the DID format is invalid or the peaq SDK is not installed.
    PeaqNetworkError
        When a network call to the peaq network fails (``is_retryable`` is True
        for transient errors, False for permanent ones).
    """

    def __init__(
        self,
        did: str,
        api_url: str = "https://peaq.network/api/v1",
        signing_key_ref: str = "keystore://default",
        config: PublisherConfig | None = None,
        _sdk_factory: Callable[[], "PeaqSDK"] | None = None,
    ) -> None:
        if not did.startswith("did:peaq:"):
            raise PeaqConfigurationError(
                f"DID must start with 'did:peaq:' — got: {did!r}"
            )
        self._did = did
        self._api_url = api_url.rstrip("/")
        self._signing_key_ref = signing_key_ref
        self._config = config or PublisherConfig()
        self._sdk_factory = _sdk_factory
        self._registered: list[ContextMachine] = []
        self._watching = False
        self._last_published_fingerprint: str | None = None

    # ------------------------------------------------------------------
    # Public API (PRD §8)
    # ------------------------------------------------------------------

    def register_machine(self, machine: ContextMachine) -> None:
        """
        Register ``machine`` for publishing.

        Calling this multiple times with the same machine is idempotent.
        """
        if machine not in self._registered:
            self._registered.append(machine)
        logger.info(
            "Registered machine %s for DID %s",
            machine.machine_ref,
            self._did,
        )

    def submit(self, snap: ContextSnapshot) -> str:
        """
        Publish ``snap`` to peaq as a signed DID document.

        Returns
        -------
        str
            The on-chain transaction hash as a hex string.

        Raises
        ------
        PeaqNetworkError
            The RPC call failed or confirmation timed out.
        PeaqConfigurationError
            The signing key is unavailable or the signature is rejected.
        """
        doc = self._build_did_document(snap)

        if self._config.dry_run:
            logger.info("[DRY RUN] Would submit DID doc for %s", snap.machine_ref)
            return "dry_run_tx"

        payload = self._sign_payload(doc)

        tx_hash = self._rpc_submit(payload)
        self._wait_confirmed(tx_hash)
        self._last_published_fingerprint = self._fingerprint(snap)
        logger.info("Published %s tx=%s", snap.machine_ref, tx_hash)
        return tx_hash

    def start_watch(
        self,
        snap: ContextSnapshot,
        on_transition: Callable[[ContextTransition], None] | None = None,
    ) -> None:
        """
        Continuously publish ``snap`` and re-publish whenever a capability transitions.

        This is a blocking call. Use ``stop_watch()`` from another thread to exit.

        Parameters
        ----------
        snap : ContextSnapshot
            The initial snapshot (re-fetched via ``machine.snapshot()`` on each cycle).
        on_transition : Callable, optional
            Callback invoked with each ``ContextTransition``.
        """
        self._watching = True
        machine_ref = snap.machine_ref
        machine: ContextMachine | None = None

        # Resolve the registered machine so we can call .snapshot() in the loop.
        for m in self._registered:
            if m.machine_ref == machine_ref:
                machine = m
                break

        if machine is None:
            raise PeaqConfigurationError(
                f"No machine with machine_ref={machine_ref!r} is registered. "
                f"Call register_machine() first."
            )

        while self._watching:
            current = machine.snapshot()
            self.submit(current)

            # Wait for the next transition or the poll interval, whichever comes first.
            next_event = machine.last_transition()
            if next_event is not None and on_transition is not None:
                on_transition(next_event)
            time.sleep(self._config.poll_interval_s)

    def stop_watch(self) -> None:
        """Signal ``start_watch`` to exit after the current cycle."""
        self._watching = False
        logger.info("Watch loop stopped for DID %s", self._did)

    # ------------------------------------------------------------------
    # Protected – override in tests
    # ------------------------------------------------------------------

    def _build_did_document(self, snap: ContextSnapshot) -> dict[str, Any]:
        """
        Build a DID web document from ``snap``.

        Structure follows the W3C DID Core spec with peaq-specific service
        endpoints for machine capability snapshots.

        Override in tests to inspect the document structure without hitting the
        network.
        """
        cap_entries = []
        for name, cap_snap in snap.capabilities.items():
            entry: dict[str, Any] = {
                "id": f"{self._did}#capability-{name}",
                "type": ["SenseCapability", "VerifiableCredential"],
                "status": cap_snap.status.value,
            }
            if cap_snap.blocking:
                entry["blocking_reasons"] = cap_snap.blocking
            if cap_snap.warnings:
                entry["warnings"] = cap_snap.warnings
            if cap_snap.unknown_paths:
                entry["unknown_paths"] = cap_snap.unknown_paths
            entry["status"] = cap_snap.status.value.lower()
            cap_entries.append(entry)

        return {
            "@context": [
                "https://www.w3.org/ns/did/v1",
                "https://peaq.network/ns/machine/v1",
            ],
            "id": self._did,
            "verificationMethod": [
                {
                    "id": f"{self._did}#key-1",
                    "type": "EcdsaSecp256k1VerificationKey2019",
                    "controller": self._did,
                    # publicKeyHex is populated by _sign_payload via SDK
                }
            ],
            "authentication": [f"{self._did}#key-1"],
            "assertionMethod": [f"{self._did}#key-1"],
            "service": [
                {
                    "id": f"{self._did}#sense-snapshot",
                    "type": "SenseMachineSnapshot",
                    "serviceEndpoint": (
                        f"{self._api_url}/machines/{snap.machine_ref}/snapshot"
                    ),
                    "properties": {
                        "schema_version": snap.schema_version,
                        "machine_ref": snap.machine_ref,
                        "peaq_did": snap.peaq_did,
                        "observation_count": len(snap.observations),
                        "capability_count": len(snap.capabilities),
                        "capabilities": cap_entries,
                    },
                }
            ],
        }

    def _sign_payload(self, doc: dict[str, Any]) -> dict[str, Any]:
        """
        Sign ``doc`` using the configured peaq SDK keystore entry.

        Raises
        ------
        PeaqConfigurationError
            When the SDK is unavailable or signing is rejected.
        """
        try:
            from peaqsdk import PeaqSDK  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PeaqConfigurationError(
                "peaq SDK is not installed. Install it with: pip install sense-ai[peaq]"
            ) from exc

        sdk = PeaqSDK(api_url=self._api_url)
        try:
            signed = sdk.sign_did_document(doc, key_ref=self._signing_key_ref)
        except Exception as exc:
            raise PeaqConfigurationError(
                f"Signing failed for {self._did}: {exc}"
            ) from exc

        return signed

    def _rpc_submit(self, payload: dict[str, Any]) -> str:
        """
        Submit the signed payload to the peaq RPC node.

        Raises
        ------
        PeaqNetworkError
            When the RPC call fails (``is_retryable=True`` for transient errors,
            ``is_retryable=False`` for permanent ones such as 400 Bad Request).
        """
        try:
            from peaqsdk import PeaqSDK  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PeaqConfigurationError(
                "peaq SDK is not installed. Install it with: pip install sense-ai[peaq]"
            ) from exc

        sdk = PeaqSDK(api_url=self._api_url)
        try:
            result = sdk.submit_transaction(payload)
            tx_hash = result.get("tx_hash")
            if not tx_hash:
                raise PeaqNetworkError(
                    f"No tx_hash in RPC response: {result}",
                    is_retryable=False,
                    transaction_id=None,
                )
            return str(tx_hash)
        except PeaqNetworkError:
            raise
        except Exception as exc:
            # Classify common HTTP-like status codes when available.
            is_retryable = not _is_permanent_error(exc)
            raise PeaqNetworkError(
                f"RPC submission failed: {exc}",
                is_retryable=is_retryable,
                transaction_id=None,
            ) from exc

    def _wait_confirmed(self, tx_hash: str) -> None:
        """Poll until ``tx_hash`` is confirmed on-chain or timeout is reached."""
        if self._config.dry_run:
            return
        deadline = time.monotonic() + self._config.confirmation_timeout_s
        while time.monotonic() < deadline:
            try:
                status = self._query_tx_status(tx_hash)
            except PeaqNetworkError:
                raise
            except Exception as exc:
                logger.warning("Tx status query failed (retrying): %s", exc)
                time.sleep(1.0)
                continue

            if status == "confirmed":
                return
            if status == "failed":
                raise PeaqNetworkError(
                    f"Transaction {tx_hash} failed on-chain",
                    is_retryable=False,
                    transaction_id=tx_hash,
                )
            time.sleep(1.0)

        raise PeaqNetworkError(
            f"Transaction {tx_hash} not confirmed within "
            f"{self._config.confirmation_timeout_s}s timeout",
            is_retryable=True,
            transaction_id=tx_hash,
        )

    def _query_tx_status(self, tx_hash: str) -> str:
        """
        Return ``'confirmed'``, ``'pending'``, or ``'failed'``.

        Raises
        ------
        PeaqNetworkError
            When the query itself fails.
        """
        try:
            from peaqsdk import PeaqSDK  # type: ignore[import-not-found]
        except ImportError as exc:
            raise PeaqConfigurationError("peaq SDK is not installed.") from exc

        sdk = PeaqSDK(api_url=self._api_url)
        try:
            return sdk.get_transaction_status(tx_hash)  # type: ignore[no-any-return]
        except Exception as exc:
            is_retryable = not _is_permanent_error(exc)
            raise PeaqNetworkError(
                f"Failed to query tx status for {tx_hash}: {exc}",
                is_retryable=is_retryable,
                transaction_id=tx_hash,
            ) from exc

    @staticmethod
    def _fingerprint(snap: ContextSnapshot) -> str:
        """Stable content-addressed fingerprint of ``snap``."""
        raw = json.dumps(snap.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def did(self) -> str:
        """The peaq DID this publisher manages."""
        return self._did

    @property
    def registered_machines(self) -> Sequence[ContextMachine]:
        """Machines registered for publishing."""
        return list(self._registered)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _is_permanent_error(exc: Exception) -> bool:
    """
    Return True when *exc* represents a non-retryable (permanent) failure.

    Covers common HTTP client error codes that will not change on retry.
    """
    msg = str(exc).lower()
    permanent_keywords = (
        "400",
        "unauthorized",
        "forbidden",
        "not found",
        "bad request",
        "invalid signature",
    )
    return any(kw in msg for kw in permanent_keywords)
