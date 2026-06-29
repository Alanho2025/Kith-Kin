from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.constants import CardActionType, CardRiskLevel
from app.domain.confirmation import CardSelectCommand
from app.domain.credentials import TrustedRequestContext
from app.repositories.confirmation_repository import InMemoryConfirmationRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.session_repository import SQLiteSessionStore
from app.repositories.visit_repository import VisitRepository
from app.schemas.cards import CardAction, CardSet, CardType, ResponseCard
from app.schemas.runtime_events import TranscriptFinalEvent, TranscriptPayload
from app.services.card_service import CardService
from app.services.session_service import SessionService
from app.services.visit_completion_service import VisitCompletionExecutor, VisitCompletionService
from tests.fixtures.clock import MutableClock

TEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 6, 22, tzinfo=UTC)


@pytest.mark.anyio
async def test_memory_write_confirmation(db_sessions, first_visit_transcript) -> None:
    clock = MutableClock()
    session_store = SQLiteSessionStore(db_sessions)
    memory_repo = MemoryRepository(db_sessions, clock.now)
    notification_repo = NotificationRepository(db_sessions, clock.now)
    visit_repo = VisitRepository(db_sessions)

    session_service = SessionService(session_store, clock.now, visit_repo)

    session_events = []

    def get_session_events(sid: UUID):
        return session_events

    from app.services.visit_summary_service import VisitSummaryService
    from app.adapters.notification_adapter import NotificationAdapter
    from app.services.notification_service import NotificationService

    visit_summary_service = VisitSummaryService()
    notification_adapter = NotificationAdapter()
    notification_service = NotificationService(notification_repo, notification_adapter)

    completion_service = VisitCompletionService(
        memory_repository=memory_repo,
        visit_summary_service=visit_summary_service,
        notification_service=notification_service,
        clock=clock.now,
        get_session_events=get_session_events,
    )


    confirmation_repository = InMemoryConfirmationRepository()
    completion_executor = VisitCompletionExecutor(completion_service, confirmation_repository)

    card_service = CardService(
        clock=clock.now,
        executor=completion_executor,
        repository=confirmation_repository,
    )

    session = await session_service.create(user_id=TEST_USER_ID, encounter_type="pharmacy")
    context = TrustedRequestContext(
        session_id=session.session_id, user_id=TEST_USER_ID, origin="test"
    )

    prov_evt = first_visit_transcript[0]
    event = TranscriptFinalEvent(
        schema_version="0.1",
        event_id=f"evt_{uuid4()}",
        event_type="transcript.final",
        session_id=str(session.session_id),
        sequence=1,
        timestamp=clock.now(),
        correlation_id=None,
        payload=TranscriptPayload(
            utterance_id=prov_evt.utterance_id,
            speaker=prov_evt.speaker,
            language=prov_evt.language,
            text=prov_evt.text,
            revision=prov_evt.revision,
        ),
    )
    session_events.append(event.model_dump(mode="json"))

    # 1. Draft is prepared, but not confirmed yet
    await completion_service.prepare_summary(session.session_id, context)

    # DB remains empty at this point
    recent_visits = await visit_repo.recent_for_user(TEST_USER_ID)
    assert len(recent_visits) == 0

    # 2. Select card (still pending confirmation)
    card_set_id = f"cards_{uuid4()}"
    save_card = ResponseCard(
        card_id=f"card_{uuid4()}",
        card_type=CardType.MEMORY_ACTION,
        zh_text="保存记忆",
        en_text="Save to memory",
        risk_level=CardRiskLevel.NORMAL,
        action=CardAction(type=CardActionType.SAVE_MEMORY),
        requires_parent_confirmation=True,
        requires_guardian_approval=True,
        guardian_decision_id=f"guardian_{uuid4()}",
    )
    card_set = CardSet(
        card_set_id=card_set_id,
        revision=1,
        source_event_id=event.event_id,
        generated_at=clock.now(),
        expires_at=clock.now() + timedelta(minutes=3),
        cards=(save_card,),
    )
    card_service.register_card_set(card_set, context)

    selected = await card_service.select(
        CardSelectCommand(card_set_id=card_set_id, card_id=save_card.card_id, revision=1),
        context,
    )

    # DB still empty
    recent_visits = await visit_repo.recent_for_user(TEST_USER_ID)
    assert len(recent_visits) == 0

    # 3. Confirm card -> triggers memory write
    await card_service.confirm_selected(selected.confirmation_id, context)

    # Now it is persisted
    recent_visits = await visit_repo.recent_for_user(TEST_USER_ID)
    assert len(recent_visits) == 1
    assert recent_visits[0].value["mentioned_drugs"] == ["coenzyme q10"]
