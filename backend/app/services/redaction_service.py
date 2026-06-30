"""Redaction service to scrub PII and credentials from logs and traces."""

import re
from typing import Any

# PII and credentials patterns
CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
MEDICARE_PATTERN = re.compile(r"\b\d{4}[ -]?\d{5}[ -]?\d\b")
PASSPORT_PATTERN = re.compile(r"\b[A-Z0-9]{8,9}\b")
GENERIC_PII_KEYS = {"card", "password", "secret", "cvv", "medicare", "passport"}


class RedactionService:
    """Detect and mask sensitive PII (payment, identity credentials) with [REDACTED]."""

    def redact_text(self, text: str) -> str:
        """Replace card, Medicare, and passport numbers in text with [REDACTED]."""
        if not text:
            return text

        # Redact cards
        text = CARD_PATTERN.sub("[REDACTED]", text)
        # Redact Medicare
        text = MEDICARE_PATTERN.sub("[REDACTED]", text)
        # Redact Passport numbers (only if alphanumeric)
        # We can be slightly conservative: if it looks like a typical 8-9 char code
        # let's only redact if it starts with characters typical of passports
        text = PASSPORT_PATTERN.sub("[REDACTED]", text)

        return text

    def redact_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Deeply redact sensitive values inside log/trace payloads."""
        cleaned: dict[str, Any] = {}
        for k, v in payload.items():
            key_lower = k.lower()
            if any(pii_key in key_lower for pii_key in GENERIC_PII_KEYS):
                cleaned[k] = "[REDACTED]"
            elif isinstance(v, str):
                cleaned[k] = self.redact_text(v)
            elif isinstance(v, dict):
                cleaned[k] = self.redact_payload(v)
            elif isinstance(v, list):
                cleaned[k] = [
                    self.redact_payload(item) if isinstance(item, dict)
                    else (self.redact_text(item) if isinstance(item, str) else item)
                    for item in v
                ]
            else:
                cleaned[k] = v
        return cleaned
