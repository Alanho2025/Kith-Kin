"""Demo-grade tracker for pharmacist-stated product options."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any


class PharmacyProductOptionTracker:
    """Track only pharmacist-stated product facts for the current session.

    This is intentionally narrow for the two-week pharmacy demo. It extracts
    facts from the scripted pharmacist template and does not infer suitability,
    similarity, ranking, or recommendations.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, str | None]]] = {}

    def discard_session(self, session_id: str) -> None:
        """Drop tracked product options for a session."""
        self._sessions.pop(session_id, None)

    def update(self, session_id: str, pharmacist_text: str) -> dict[str, Any] | None:
        """Update product facts from one pharmacist utterance.

        Args:
            session_id: Stable session identifier.
            pharmacist_text: One pharmacist-stated transcript.

        Returns:
            A snapshot when product facts are present or changed; otherwise None.
        """
        text = " ".join(pharmacist_text.strip().split())
        if not text:
            return None

        changed = False
        options = self._sessions.get(session_id)
        parsed_names = _parse_three_option_names(text)
        if parsed_names:
            options = [_empty_option(name) for name in parsed_names]
            self._sessions[session_id] = options
            changed = True

        options = self._sessions.get(session_id)
        if not options:
            return None

        if _apply_detail_sentences(options, text):
            changed = True
        if _apply_prices(options, text):
            changed = True

        if not changed:
            return None
        return {"options": deepcopy(options)}


def _empty_option(name: str) -> dict[str, str | None]:
    return {
        "name": name,
        "price": None,
        "pharmacist_stated_use": None,
        "pharmacist_stated_directions": None,
        "pharmacist_stated_cautions": None,
    }


def _parse_three_option_names(text: str) -> list[str]:
    lowered = text.lower()
    if "three options" not in lowered:
        return []

    colon_match = re.search(r"three options:\s*(.+?)(?:\.|$)", text, flags=re.IGNORECASE)
    if colon_match:
        segment = colon_match.group(1)
        segment = re.sub(r"\band\s+a\s+cheaper\s+", "and ", segment, flags=re.IGNORECASE)
        parts = [part.strip(" ,") for part in re.split(r",\s*|\s+and\s+", segment)]
        names: list[str] = []
        for part in parts:
            clean = re.sub(
                r"^(?:and\s+)?(?:(?:a|an|the)\s+)?(?:cheaper\s+)?",
                "",
                part,
                flags=re.IGNORECASE,
            )
            clean = re.split(r"\s+which\s+is\s+", clean, flags=re.IGNORECASE)[0]
            name = clean.strip(" ,.")
            if name:
                names.append(name)
        return names[:3] if len(names) >= 3 else []

    matches = re.findall(r"(?:this one is|and this one is)\s+(?:a\s+|an\s+)?([^,.]+)", lowered)
    names = [match.strip() for match in matches]
    return names[:3] if len(names) >= 3 else []


def _apply_detail_sentences(options: list[dict[str, str | None]], text: str) -> bool:
    changed = False
    sentences = [sentence.strip(" .") for sentence in re.split(r"\.\s+", text) if sentence.strip()]
    for sentence in sentences:
        lowered = sentence.lower()
        for option in options:
            name = str(option["name"])
            name_lower = name.lower()
            prefix = f"{name_lower} is "
            directions_prefix = f"{name_lower} directions are "
            article_prefix = f"the {name_lower} "
            inline_use = re.search(
                rf"\b{re.escape(name)}\s+which\s+is\s+([^,.;]+)",
                sentence,
                flags=re.IGNORECASE,
            )
            if inline_use:
                detail = inline_use.group(1).strip(" .")
                if detail and option["pharmacist_stated_use"] != detail:
                    option["pharmacist_stated_use"] = detail
                    changed = True
            if lowered.startswith(prefix):
                detail = sentence[len(prefix):].strip(" .")
                if detail and option["pharmacist_stated_use"] != detail:
                    option["pharmacist_stated_use"] = detail
                    changed = True
            elif lowered.startswith(directions_prefix):
                detail = sentence[len(directions_prefix):].strip(" .")
                if detail and option["pharmacist_stated_directions"] != detail:
                    option["pharmacist_stated_directions"] = detail
                    changed = True
            elif lowered.startswith(article_prefix):
                detail = sentence[len(article_prefix):].strip(" .")
                if re.match(r"price\s+is\s+\d+(?:\.\d{1,2})?\s+dollars\b", detail.lower()):
                    price = detail.split("is", maxsplit=1)[1].strip(" .")
                    if price and option["price"] != price:
                        option["price"] = price
                        changed = True
                elif detail and option["pharmacist_stated_cautions"] != detail:
                    option["pharmacist_stated_cautions"] = detail
                    changed = True
            elif lowered.startswith(f"{name_lower} may "):
                detail = sentence[len(name) + 1:].strip(" .")
                if detail and option["pharmacist_stated_cautions"] != detail:
                    option["pharmacist_stated_cautions"] = detail
                    changed = True
    return changed


def _apply_prices(options: list[dict[str, str | None]], text: str) -> bool:
    lowered = text.lower()
    if "price" not in lowered:
        return False
    prices = re.findall(r"\b\d+(?:\.\d{1,2})?\s+dollars\b", lowered)
    if len(prices) < len(options):
        return False
    changed = False
    for option, price in zip(options, prices, strict=False):
        if option["price"] != price:
            option["price"] = price
            changed = True
    return changed
