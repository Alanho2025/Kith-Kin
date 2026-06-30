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
    # These categories are never auto-disclosed through response cards because a
    # parent confirmation click is not enough to make them safe in a pharmacy line.
    if category in {
        SensitiveDataCategory.IDENTITY,
        SensitiveDataCategory.PAYMENT,
        SensitiveDataCategory.ADDRESS,
    }:
        return SafetyDecision.BLOCK
    # Health and family follow-up data require both model-side Guardian approval
    # and an explicit parent confirmation before any outward action.
    if guardian_approved and parent_confirmed:
        return SafetyDecision.ALLOW
    return SafetyDecision.REQUIRE_CONFIRMATION


def screen_turn_text(text: str) -> tuple[SafetyBackstopResult, BackstopRisk, BackstopReason]:
    """Detect sensitive or unsafe requests without relying on a model."""
    lowered = text.lower()
    prompt_markers = ("ignore previous", "system prompt", "developer message")
    if any(marker in lowered for marker in prompt_markers):
        # Prompt-injection language is blocked before agent routing so the model
        # never gets a chance to reinterpret system or developer instructions.
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.PROMPT_INJECTION,
        )
    if any(marker in lowered for marker in ("api key", "password", "secret", "token")):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.IDENTITY_REQUEST,
        )
    if any(
        marker in lowered
        for marker in (
            "save the summary",
            "save this",
            "send this to my daughter",
            "send this to my son",
            "send this to my family",
            "notify family",
        )
    ):
        # Save/send requests are not blocked outright, but they must flow through
        # the two-stage confirmation path before persistence or notification.
        return (
            SafetyBackstopResult.REQUIRE_CONFIRMATION,
            BackstopRisk.MEDICAL,
            BackstopReason.MEDICAL_ADVICE,
        )
    if any(
        marker in lowered
        for marker in (
            "credit card",
            "card number",
            "cvv",
            "bsb",
            "bank account",
            "account number",
        )
    ):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.PAYMENT_REQUEST,
        )
    if any(
        marker in lowered
        for marker in (
            "passport",
            "medicare",
            "driver licence",
            "driver's licence",
            "drivers licence",
            "driver license",
            "driver's license",
            "drivers license",
            "driving licence",
        )
    ):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.IDENTITY_REQUEST,
        )
    if any(
        marker in lowered
        for marker in (
            "home address",
            "where do you live",
            "street address",
            "residential address",
            "your address",
        )
    ):
        return (
            SafetyBackstopResult.BLOCK,
            BackstopRisk.PRIVACY,
            BackstopReason.ADDRESS_REQUEST,
        )
    passive_medical_explanation_markers = (
        "may make you sleepy",
        "avoid driving",
    )
    if any(marker in lowered for marker in passive_medical_explanation_markers):
        # Pharmacist-provided warnings can be translated passively; the app is
        # not making a new medical recommendation in this case.
        return SafetyBackstopResult.ALLOW, BackstopRisk.NORMAL, BackstopReason.NONE
    medical_confirmation_markers = (
        "stop taking",
        "change your dose",
        "take double",
        "ibuprofen",
        "lisinopril",
        "medicine",
        "medication",
        "drug",
        "take this",
        "headache",
        "allergy",
        "allergies",
        "antibiotic",
        "dose",
        "prescription",
        "refill",
        "药",
        "降血压",
    )
    if any(marker in lowered for marker in medical_confirmation_markers):
        # Medication terms route to confirmation/card handling so Kith&Kin
        # supports clarification without making autonomous clinical decisions.
        return (
            SafetyBackstopResult.REQUIRE_CONFIRMATION,
            BackstopRisk.MEDICAL,
            BackstopReason.MEDICAL_ADVICE,
        )
    return SafetyBackstopResult.ALLOW, BackstopRisk.NORMAL, BackstopReason.NONE
