"""
Typed error model — FR-14.

All public SDK exceptions inherit from SenseError. Callers may catch the
base class to handle any SDK error, or catch a specific subclass to react
to a known failure mode.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class SenseError(Exception):
    """
    Base class for every public Sense exception.

    Subclasses are organised by the layer that raises them:

    *Schema* — validation of inbound telemetry against a versioned JSON Schema.
    *Rule*   — construction or evaluation of capability constraint rules.
    *Model*  — use of capabilities, snapshots, or observations at runtime.
    *Peaq*   — configuration, network, or unsupported-flow errors in the
               peaq integration layer.
    *Serialization* — JSON encoding / decoding failures.
    """

    pass


# ---------------------------------------------------------------------------
# Schema-layer errors (FR-2 / FR-3)
# ---------------------------------------------------------------------------


class SchemaValidationError(SenseError):
    """
    Raised when an inbound telemetry payload fails JSON Schema validation.

    Attributes
    ----------
    schema_version : str
        The ``$schema`` version the payload was validated against.
    json_path : str
        JSON Pointer path to the failing node inside the document
        (e.g. ``"/observations/0/path"``).
    message : str
        Human-readable validation failure description.
    value : object
        The value that failed validation (not serialised if it is large).
    """

    def __init__(
        self,
        message: str,
        *,
        schema_version: str | None = None,
        json_path: str = "",
        value: object = None,
    ) -> None:
        self.message = message
        self.schema_version = schema_version
        self.json_path = json_path
        self.value = value
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"SchemaValidationError({self.message!r}, "
            f"schema_version={self.schema_version!r}, "
            f"json_path={self.json_path!r})"
        )


# ---------------------------------------------------------------------------
# Rule-layer errors (FR-5)
# ---------------------------------------------------------------------------


class InvalidRuleError(SenseError):
    """
    Raised when a rule expression cannot be evaluated.

    Covers syntactically malformed expressions, references to unknown
    capability paths, type mismatches at evaluation time, and cycles
    in composed expressions.

    Attributes
    ----------
    rule_repr : str
        Human-readable representation of the problematic rule.
    capability_path : str | None
        The capability path involved, if known.
    """

    def __init__(
        self,
        message: str,
        *,
        rule_repr: str | None = None,
        capability_path: str | None = None,
    ) -> None:
        self.rule_repr = rule_repr
        self.capability_path = capability_path
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"InvalidRuleError({self.rule_repr!r}, "
            f"capability_path={self.capability_path!r})"
        )


# ---------------------------------------------------------------------------
# Model-layer errors
# ---------------------------------------------------------------------------


class UnknownCapabilityError(SenseError):
    """
    Raised when a capability is referenced but has not been registered.

    Attributes
    ----------
    capability_id : str
        The capability identifier that was not found.
    available_ids : tuple[str, ...]
        Currently registered capability IDs (may be empty).
    """

    def __init__(
        self,
        capability_id: str,
        *,
        available_ids: tuple[str, ...] = (),
    ) -> None:
        self.capability_id = capability_id
        self.available_ids = available_ids
        message = (
            f"Capability {capability_id!r} is not registered. "
            f"Available: {available_ids!r}"
        )
        super().__init__(message)


class MissingEvidenceError(SenseError):
    """
    Raised when a capability evaluation cannot proceed because required
    telemetry is absent or too stale.

    Attributes
    ----------
    capability_id : str
        The capability whose evaluation is blocked.
    missing_paths : tuple[str, ...]
        Telemetry paths that have no recent observation.
    """

    def __init__(
        self,
        capability_id: str,
        *,
        missing_paths: tuple[str, ...] = (),
    ) -> None:
        self.capability_id = capability_id
        self.missing_paths = missing_paths
        message = (
            f"Capability {capability_id!r} cannot be evaluated: "
            f"missing evidence for {missing_paths!r}"
        )
        super().__init__(message)


# ---------------------------------------------------------------------------
# Serialization errors
# ---------------------------------------------------------------------------


class SerializationError(SenseError):
    """
    Raised when a ContextSnapshot cannot be serialised to or from JSON.

    Covers JSON encoding/decoding failures and versioned schema
    resolution errors.

    Attributes
    ----------
    schema_version : str | None
        The schema version involved, if known.
    """

    def __init__(
        self,
        message: str,
        *,
        schema_version: str | None = None,
    ) -> None:
        self.schema_version = schema_version
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"SerializationError({str(self)!r}, schema_version={self.schema_version!r})"
        )


# ---------------------------------------------------------------------------
# Peaq-layer errors (FR-10)
# ---------------------------------------------------------------------------


class PeaqConfigurationError(SenseError):
    """
    Raised when the peaq integration is mis-configured.

    Covers missing or malformed peaq DID, machine-ref, network-endpoint,
    or any other required peaq configuration parameter.
    """

    pass


class PeaqNetworkError(SenseError):
    """
    Raised when a network call to the peaq network fails.

    The ``is_retryable`` flag distinguishes transient failures
    (e.g. a timeout or 503) that may succeed on retry from permanent
    failures (e.g. 400 Bad Request, 404 Not Found).

    Attributes
    ----------
    is_retryable : bool
        True if the error is likely to succeed on retry.
    transaction_id : str | None
        peaq network transaction identifier, if returned by the peer.
    """

    def __init__(
        self,
        message: str,
        *,
        is_retryable: bool = True,
        transaction_id: str | None = None,
    ) -> None:
        self.is_retryable = is_retryable
        self.transaction_id = transaction_id
        super().__init__(message)

    def __repr__(self) -> str:
        return (
            f"PeaqNetworkError({str(self)!r}, "
            f"is_retryable={self.is_retryable}, "
            f"transaction_id={self.transaction_id!r})"
        )


class UnsupportedPeaqFlowError(SenseError):
    """
    Raised when an unsupported peaq workflow is invoked.

    For example, requesting a DID registration flow when only
    the verification flow is implemented.
    """

    pass
