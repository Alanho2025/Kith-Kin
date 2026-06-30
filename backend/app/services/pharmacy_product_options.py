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

    natural_names = [
        match.group("name").strip()
        for match in re.finditer(
            r"\b(?P<name>[A-Z][A-Za-z]*(?:\s+(?:gel|cream|tablet|tablets|capsule|capsules|syrup|spray))?)\s+costs\s+",
            text,
        )
    ]
    if len(natural_names) >= 3:
        return natural_names[:3]

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
            natural = re.search(
                rf"\b{re.escape(name)}\s+costs\s+"
                r"(?P<price>\d+(?:\.\d{1,2})?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)"
                r"\s+dollars?\s+and\s+is\s+for\s+(?P<detail>.+)$",
                sentence,
                flags=re.IGNORECASE,
            )
            if natural:
                price = f"{_number_word_to_digits(natural.group('price'))} dollars"
                if option["price"] != price:
                    option["price"] = price
                    changed = True
                detail = natural.group("detail").strip(" .")
                caution = None
                if ";" in detail:
                    detail, caution = [part.strip(" .") for part in detail.split(";", maxsplit=1)]
                if ", but " in detail.lower():
                    parts = re.split(r",\s+but\s+", detail, maxsplit=1, flags=re.IGNORECASE)
                    detail = parts[0].strip(" .")
                    caution = parts[1].strip(" .")
                if detail and option["pharmacist_stated_use"] != detail:
                    option["pharmacist_stated_use"] = detail
                    changed = True
                if caution and option["pharmacist_stated_cautions"] != caution:
                    option["pharmacist_stated_cautions"] = caution
                    changed = True
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
    if "price" not in lowered and "costs" not in lowered:
        return False
    prices = re.findall(
        r"\b(?:\d+(?:\.\d{1,2})?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\s+dollars\b",
        lowered,
    )
    if len(prices) < len(options):
        return False
    changed = False
    for option, price in zip(options, prices, strict=False):
        amount = price.split()[0]
        price = f"{_number_word_to_digits(amount)} dollars"
        if option["price"] != price:
            option["price"] = price
            changed = True
    return changed


def _number_word_to_digits(value: str) -> str:
    words = {
        "one": "1",
        "two": "2",
        "three": "3",
        "four": "4",
        "five": "5",
        "six": "6",
        "seven": "7",
        "eight": "8",
        "nine": "9",
        "ten": "10",
        "eleven": "11",
        "twelve": "12",
        "thirteen": "13",
        "fourteen": "14",
        "fifteen": "15",
        "sixteen": "16",
        "seventeen": "17",
        "eighteen": "18",
        "nineteen": "19",
        "twenty": "20",
    }
    return words.get(value.lower(), value)
