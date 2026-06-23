from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.constants import CardActionType, CardRiskLevel
from app.db.models.notification import Notification
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
async def test_notification_confirmation(
    db_sessions, first_visit_transcript, local_family_destination
) -> None:
    clock = MutableClock()
    session_store = SQLiteSessionStore(db_sessions)
    memory_repo = MemoryRepository(db_sessions, clock.now)
    notification_repo = NotificationRepository(db_sessions, clock.now)
    visit_repo = VisitRepository(db_sessions)
    
    session_service = SessionService(session_store, clock.now, visit_repo)
    
    session_events = []
    def get_session_events(sid: UUID):
        return session_events

    completion_service = VisitCompletionService(
        memory_repository=memory_repo,
        notification_repository=notification_repo,
        get_session_events=get_session_events,
    )
    
    confirmation_repository = InMemoryConfirmationRepository()
    completion_executor = VisitCompletionExecutor(completion_service, confirmation_repository)
    
    card_service = CardService(
        clock=clock.now,
        executor=completion_executor,
        repository=confirmation_repository,
    )
    
    # Verify user profile has the expected local family contact label
    async with db_sessions() as session:
        from app.db.models.user import User
        user = await session.get(User, TEST_USER_ID)
        assert user.family_contact_label == local_family_destination
    
    session_record = await session_service.create(user_id=TEST_USER_ID, encounter_type="pharmacy")
    context = TrustedRequestContext(
        session_id=session_record.session_id, user_id=TEST_USER_ID, origin="test"
    )
    
    prov_evt = first_visit_transcript[0]
    event = TranscriptFinalEvent(
        schema_version="0.1",
        event_id=f"evt_{uuid4()}",
        event_type="transcript.final",
        session_id=str(session_record.session_id),
        sequence=1,
        timestamp=clock.now(),
        correlation_id=None,
        payload=TranscriptPayload(
            utterance_id=prov_evt.utterance_id,
            speaker=prov_evt.speaker,
            language=prov_evt.language,
            text=prov_evt.text,
            revision=prov_evt.revision,
        )
    )
    session_events.append(event.model_dump(mode="json"))
    
    # 1. Prepare draft summary
    await completion_service.prepare_summary(session_record.session_id, context)
    
    # 2. Register, select, and confirm NOTIFY_FAMILY card
    card_set_id = f"cards_{uuid4()}"
    notify_card = ResponseCard(
        card_id=f"card_{uuid4()}",
        card_type=CardType.FAMILY_ACTION,
        zh_text="发送通知",
        en_text="Notify family",
        risk_level=CardRiskLevel.NORMAL,
        action=CardAction(type=CardActionType.NOTIFY_FAMILY),
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
        cards=(notify_card,),
    )
    card_service.register_card_set(card_set, context)
    
    selected = await card_service.select(
        CardSelectCommand(card_set_id=card_set_id, card_id=notify_card.card_id, revision=1),
        context,
    )
    
    # Confirming triggers the send_stub operation on the notification repository
    await card_service.confirm_selected(selected.confirmation_id, context)
    
    # Verify the notification is audited in the db
    async with db_sessions() as session:
        notif = await session.scalar(
            select(Notification).where(Notification.session_id == session_record.session_id)
        )
        assert notif is not None
        assert notif.provider == "stub"
        assert notif.status == "delivered"
        assert notif.summary["mentioned_drugs"] == ["coenzyme q10"]
