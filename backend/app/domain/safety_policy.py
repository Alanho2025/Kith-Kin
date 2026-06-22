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


class BackstopReason(StrEnum):
    """Stable deterministic Guardian backstop reasons."""

    NONE = "none"
    PAYMENT_REQUEST = "payment_request"
    IDENTITY_REQUEST = "identity_request"
    ADDRESS_REQUEST = "address_request"
    PROMPT_INJECTION = "prompt_injection"
    MEDICAL_ADVICE = "medical_advice"


class BackstopRisk(StrEnum):
    """Risk levels emitted by the deterministic backstop."""

    NORMAL = "normal"
    PRIVACY = "privacy"
    MEDICAL = "medical"


class SafetyBackstopResult(StrEnum):
    """Fail-closed deterministic screening result."""

    ALLOW = "allow"
    BLOCK = "block"
    REQUIRE_CONFIRMATION = "require_confirmation"


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


def screen_turn_text(text: str) -> tuple[SafetyBackstopResult, BackstopRisk, BackstopReason]:
    """Detect sensitive or unsafe requests without relying on a model."""
    lowered = text.lower()
    prompt_markers = ("ignore previous", "system prompt", "developer message")
    if any(marker in lowered for marker in prompt_markers):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.PROMPT_INJECTION,
        )
    if any(marker in lowered for marker in ("credit card", "card number", "cvv")):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.PAYMENT_REQUEST,
        )
    if any(marker in lowered for marker in (
        "passport",
        "medicare",
        "driver licence",
        "driver's licence",
        "drivers licence",
        "driver license",
        "driver's license",
        "drivers license",
        "driving licence",
    )):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.IDENTITY_REQUEST,
        )
    if any(marker in lowered for marker in ("home address", "where do you live", "street address")):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.ADDRESS_REQUEST,
        )
    medical_confirmation_markers = (
        "stop taking",
        "change your dose",
        "take double",
        "ibuprofen",
        "lisinopril",
        "medicine",
        "medication",
        "drug",
        "allergy",
        "allergies",
        "antibiotic",
        "dose",
    )
    if any(marker in lowered for marker in medical_confirmation_markers):
        return (
            SafetyBackstopResult.REQUIRE_CONFIRMATION,
            BackstopRisk.MEDICAL,
            BackstopReason.MEDICAL_ADVICE,
        )
    return SafetyBackstopResult.ALLOW, BackstopRisk.NORMAL, BackstopReason.NONE