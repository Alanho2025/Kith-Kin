"""Visit completion service to compile and persist visit summaries and notifications."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

from app.core.constants import CardActionType
from app.domain.confirmation import ConfirmationOutcome, StoredConfirmation
from app.domain.credentials import TrustedRequestContext
from app.repositories.confirmation_repository import InMemoryConfirmationRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.cards import ResponseCard
from app.schemas.visit_summary import SummaryReview
from app.services.confirmed_action_executor import ConfirmedActionExecutor


class VisitCompletionService:
    """Compile session transcripts and execute approved actions (memory/notifications)."""

    def __init__(
        self,
        memory_repository: MemoryRepository,
        notification_repository: NotificationRepository,
        get_session_events: Callable[[UUID], list[dict[str, Any]]] | None = None,
    ) -> None:
        self._memory = memory_repository
        self._notifications = notification_repository
        self._get_session_events = get_session_events
        self._draft_summaries: dict[UUID, SummaryReview] = {}

    def discard_session(self, session_id: UUID) -> None:
        self._draft_summaries.pop(session_id, None)

    async def prepare_summary(
        self,
        session_id: UUID,
        context: TrustedRequestContext,
    ) -> SummaryReview:
        """Compile final transcript text and RAG context into a draft summary."""
        events = []
        if self._get_session_events is not None:
            events = self._get_session_events(session_id)

        transcripts: list[tuple[str, str]] = []
        for event in events:
            if event.get("event_type") == "transcript.final":
                payload = event.get("payload", {})
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

        summary = SummaryReview(
            mentioned_drugs=tuple(mentioned_drugs),
            pharmacist_advice_summary=pharmacist_advice_summary,
            unresolved_questions=tuple(unresolved_questions[:20]),
            follow_up_needed=follow_up_needed,
            family_notification_requested=family_notification_requested,
            pharmacist_stated_advice=pharmacist_advice_summary,
            unresolved_follow_up_questions=tuple(unresolved_questions[:20]),
            confirmed_family_follow_up=False,
        )
        self._draft_summaries[session_id] = summary
        return summary

    async def execute_confirmed_action(
        self,
        confirmation: StoredConfirmation,
        context: TrustedRequestContext,
    ) -> None:
        """Execute the confirmed card action using the prepared draft summary."""
        # 1. Retrieve draft summary or compile on-demand
        summary = self._draft_summaries.get(confirmation.session_id)
        if summary is None:
            summary = await self.prepare_summary(confirmation.session_id, context)

        # 2. Persist to SQLite memory or send to family notification stub
        if confirmation.action_type == CardActionType.SAVE_MEMORY:
            await self._memory.write_visit_summary(
                summary=summary,
                context=context,
                key=f"visit_summary:{confirmation.session_id}",
                tags=("visit_summary",),
                idempotency_key=confirmation.idempotency_key,
            )
        elif confirmation.action_type == CardActionType.NOTIFY_FAMILY:
            await self._notifications.send_stub(
                summary=summary,
                context=context,
                idempotency_key=confirmation.idempotency_key,
            )


class VisitCompletionExecutor(ConfirmedActionExecutor):
    """Subclass of ConfirmedActionExecutor that delegates SAVE_MEMORY and NOTIFY_FAMILY."""

    def __init__(
        self,
        completion_service: VisitCompletionService,
        repository: InMemoryConfirmationRepository,
    ) -> None:
        super().__init__()
        self._completion_service = completion_service
        self._repository = repository

    async def execute(
        self,
        confirmation_id: str,
        card: ResponseCard,
        context: TrustedRequestContext | None = None,
    ) -> ConfirmationOutcome:
        self.action_count += 1
        record = self._repository.get(confirmation_id)
        if record is not None and context is not None:
            await self._completion_service.execute_confirmed_action(record, context)
        return ConfirmationOutcome(
            confirmation_id=confirmation_id,
            action_type=card.action.type,
            replayed=False,
            phase="succeeded",
            code=None,
        )


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


def _normalise_space(text: str) -> str:
    return " ".join(text.strip().split())
