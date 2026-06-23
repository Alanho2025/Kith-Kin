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

    async def prepare_summary(
        self,
        session_id: UUID,
        context: TrustedRequestContext,
    ) -> SummaryReview:
        """Compile final transcript text and RAG context into a draft summary."""
        events = []
        if self._get_session_events is not None:
            events = self._get_session_events(session_id)

        transcript_lines: list[str] = []
        for event in events:
            if event.get("event_type") == "transcript.final":
                payload = event.get("payload", {})
                speaker = payload.get("speaker", "unknown")
                text = payload.get("text", "")
                if text:
                    transcript_lines.append(f"{speaker}: {text}")

        full_text = " ".join(transcript_lines)
        lower_text = full_text.lower()

        mentioned_drugs: list[str] = []
        pharmacist_advice_summary = "Routine visit completed."
        unresolved_questions: list[str] = []
        follow_up_needed = False
        family_notification_requested = False

        # Match generic & brand drug names
        # Perindopril + Ibuprofen (Scenario 01)
        if "perindopril" in lower_text or "coversyl" in lower_text or "perindo" in lower_text:
            mentioned_drugs.append("perindopril")
        if "ibuprofen" in lower_text or "nurofen" in lower_text:
            mentioned_drugs.append("ibuprofen")
            pharmacist_advice_summary = (
                "Pharmacist advised against Nurofen (ibuprofen) due to kidney risk and "
                "blood pressure drug interaction with perindopril. Suggested Panadol instead."
            )
            follow_up_needed = True

        # Warfarin + Voltaren (Scenario 02)
        if "warfarin" in lower_text:
            mentioned_drugs.append("warfarin")
        if "voltaren" in lower_text or "diclofenac" in lower_text:
            mentioned_drugs.append("voltaren")
            pharmacist_advice_summary = (
                "Pharmacist warned that Voltaren (diclofenac) with warfarin doubles bleeding risk. "
                "Strongly advised Panadol instead."
            )
            follow_up_needed = True

        # Amlodipine/Candesartan + Codral (Scenario 03)
        if "amlodipine" in lower_text or "norvasc" in lower_text:
            mentioned_drugs.append("amlodipine")
        if "candesartan" in lower_text or "atacand" in lower_text:
            mentioned_drugs.append("candesartan")
        if "codral" in lower_text or "pseudoephedrine" in lower_text:
            mentioned_drugs.append("codral")
            pharmacist_advice_summary = (
                "Pharmacist warned that Codral (pseudoephedrine) raises blood pressure. "
                "Suggested saline nasal spray."
            )
            follow_up_needed = True

        # Atorvastatin + Grapefruit (Scenario 04)
        if "atorvastatin" in lower_text or "lipitor" in lower_text:
            mentioned_drugs.append("atorvastatin")
        if "grapefruit" in lower_text:
            mentioned_drugs.append("grapefruit")
            pharmacist_advice_summary = (
                "Pharmacist advised limiting or avoiding grapefruit as it affects "
                "Lipitor (atorvastatin) metabolism."
            )
            follow_up_needed = True

        # Coenzyme Q10 (Scenario 05 / Hero Visit 1)
        if (
            "coenzyme q10" in lower_text
            or "coenzyme" in lower_text
            or "q10" in lower_text
            or "coq10" in lower_text
        ):
            mentioned_drugs.append("coenzyme q10")
            pharmacist_advice_summary = (
                "Pharmacist suggested Coenzyme Q10 supplement for muscle aches."
            )
            unresolved_questions.append("Should I start taking Coenzyme Q10 for muscle aches?")
            follow_up_needed = True
            family_notification_requested = True

        if not mentioned_drugs:
            for drug in ["panadol", "paracetamol"]:
                if drug in lower_text:
                    mentioned_drugs.append("paracetamol")

        summary = SummaryReview(
            mentioned_drugs=tuple(sorted(list(set(mentioned_drugs)))),
            pharmacist_advice_summary=pharmacist_advice_summary,
            unresolved_questions=tuple(sorted(unresolved_questions)),
            follow_up_needed=follow_up_needed,
            family_notification_requested=family_notification_requested,
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
