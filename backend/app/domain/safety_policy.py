"""Pure consent policy for sensitive data and outward actions."""

from enum import StrEnum


class SensitiveDataCategory(StrEnum):
    """Data classes requiring explicit safety treatment."""

    HEALTH = "health"
    IDENTITY = "identity"
    PAYMENT = "payment"
    ADDRESS = "address"
    FAMILY = "family"


class SafetyDecision(StrEnum):
    """Deterministic pre-agent safety outcome."""

    ALLOW = "allow"
    REQUIRE_CONFIRMATION = "require_confirmation"
    BLOCK = "block"


def disclosure_decision(
    category: SensitiveDataCategory,
    *,
    guardian_approved: bool,
    parent_confirmed: bool,
) -> SafetyDecision:
    """Require both gates for health/family and block identity/payment/address disclosure."""
    if category in {
        SensitiveDataCategory.IDENTITY,
        SensitiveDataCategory.PAYMENT,
        SensitiveDataCategory.ADDRESS,
    }:
        return SafetyDecision.BLOCK
    if guardian_approved and parent_confirmed:
        return SafetyDecision.ALLOW
    return SafetyDecision.REQUIRE_CONFIRMATION
