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
