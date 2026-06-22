"""Stable application errors safe to map at transport boundaries."""


class KithKinError(Exception):
    """Base class for expected application failures."""

    code = "KITHKIN_ERROR"


class SchemaVersionUnsupportedError(KithKinError):
    """Raised when a runtime event uses an unsupported schema major."""

    code = "SCHEMA_VERSION_UNSUPPORTED"


class UntrustedIdentityError(KithKinError):
    """Raised when caller-supplied identity reaches a trusted boundary."""

    code = "UNTRUSTED_IDENTITY"


class RetrievalLimitError(KithKinError):
    """Raised when retrieval limits are invalid."""

    code = "RETRIEVAL_LIMIT_INVALID"


class SessionNotConnectableError(KithKinError):
    """Raised when a missing or ended session cannot accept a ticket/socket."""

    code = "SESSION_NOT_CONNECTABLE"


class TicketInvalidError(KithKinError):
    """Raised for missing, malformed, expired, or invalid-signature tickets."""

    code = "TICKET_INVALID"


class TicketScopeError(KithKinError):
    """Raised when a validly signed ticket is outside its bound scope."""

    code = "TICKET_SCOPE_INVALID"


class TicketReplayError(KithKinError):
    """Raised when a single-use ticket JTI has already been consumed."""

    code = "TICKET_REPLAYED"
