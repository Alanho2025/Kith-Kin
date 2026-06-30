"""Visit summary compilation and text extraction service."""

import logging
from uuid import UUID

from app.schemas.visit_summary import SummaryReview

logger = logging.getLogger(__name__)


DRUG_ALIASES: dict[str, tuple[str, ...]] = {
    "amlodipine": ("amlodipine", "norvasc"),
    "atorvastatin": ("atorvastatin", "lipitor"),
    "candesartan": ("candesartan", "atacand"),
    "codral": ("codral", "pseudoephedrine"),
    "coenzyme q10": ("coenzyme q10", "coq10", "q10"),
    "grapefruit": ("grapefruit",),
    "ibuprofen": ("ibuprofen", "nurofen"),
    "paracetamol": ("paracetamol", "panadol"),
    "perindopril": ("perindopril", "coversyl", "perindo"),
    "voltaren": ("voltaren", "diclofenac"),
    "warfarin": ("warfarin",),
}


def _extract_mentioned_drugs(text: str) -> list[str]:
    lower_text = text.lower()
    mentioned = {
        canonical
        for canonical, aliases in DRUG_ALIASES.items()
        if any(alias in lower_text for alias in aliases)
    }
    return sorted(mentioned)


def _normalise_space(text: str) -> str:
    return " ".join(text.strip().split())


def _summarize_pharmacist_lines(lines: list[str]) -> str:
    if not lines:
        return "No pharmacist medication instructions were recorded."
    summary = "Pharmacist said: " + " ".join(_normalise_space(line) for line in lines)
    if len(summary) <= 1000:
        return summary
    return f"{summary[:997].rstrip()}..."


def _looks_like_question(text: str) -> bool:
    lowered = text.strip().lower()
    if "?" in lowered or "？" in lowered:
        return True
    return lowered.startswith(
        (
            "could you",
            "can you",
            "should i",
            "would you",
            "do you",
            "does ",
            "is ",
            "are ",
            "what ",
            "which ",
            "how ",
            "when ",
            "where ",
            "why ",
        )
    )


def _has_follow_up_marker(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "ask your doctor",
            "check with your doctor",
            "talk to your doctor",
            "see your doctor",
            "ask your gp",
            "check with your gp",
            "follow up",
            "come back",
        )
    )


def _has_family_request(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "send this to my family",
            "send this summary to my family",
            "notify my family",
            "notify family",
            "tell my daughter",
            "tell my son",
            "tell my family",
        )
    )


def _unique_preserve(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        normalised = _normalise_space(item)
        key = normalised.lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(normalised)
    return unique


class VisitSummaryService:
    """Compile session transcripts and extract structured medical and recall fields."""

    def compile_summary_from_events(self, events: list[dict[str, object]]) -> SummaryReview:
        """Process transcript events to construct the final VisitSummary draft."""
        transcripts: list[tuple[str, str]] = []
        for event in events:
            if event.get("event_type") == "transcript.final":
                payload = event.get("payload", {})
                if isinstance(payload, dict):
                    speaker = payload.get("speaker", "unknown")
                    text = payload.get("text", "")
                    if isinstance(text, str) and text:
                        transcripts.append((str(speaker), text.strip()))

        all_text = " ".join(text for _speaker, text in transcripts)
        pharmacist_lines = [
            text for speaker, text in transcripts if speaker == "pharmacist"
        ]
        parent_questions = [
            text
            for speaker, text in transcripts
            if speaker == "parent" and _looks_like_question(text)
        ]

        mentioned_drugs = _extract_mentioned_drugs(all_text)
        pharmacist_advice_summary = _summarize_pharmacist_lines(pharmacist_lines)
        unresolved_questions = _unique_preserve(parent_questions)
        follow_up_needed = bool(unresolved_questions) or _has_follow_up_marker(
            pharmacist_advice_summary
        )
        family_notification_requested = _has_family_request(all_text)

        return SummaryReview(
            mentioned_drugs=tuple(mentioned_drugs),
            pharmacist_advice_summary=pharmacist_advice_summary,
            unresolved_questions=tuple(unresolved_questions[:20]),
            follow_up_needed=follow_up_needed,
            family_notification_requested=family_notification_requested,
            pharmacist_stated_advice=pharmacist_advice_summary,
            unresolved_follow_up_questions=tuple(unresolved_questions[:20]),
            confirmed_family_follow_up=False,
        )
