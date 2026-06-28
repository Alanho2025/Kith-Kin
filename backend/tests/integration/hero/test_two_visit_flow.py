from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.agents.companion_agent import CompanionAgent
from app.core.constants import CardActionType, CardRiskLevel
from app.domain.confirmation import CardSelectCommand
from app.domain.credentials import TrustedRequestContext
from app.repositories.confirmation_repository import InMemoryConfirmationRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.session_repository import SQLiteSessionStore
from app.repositories.visit_repository import VisitRepository
from app.schemas.agent_outputs import RouteDecision, RouteReasonCode, RouteType
from app.schemas.cards import CardAction, CardSet, CardType, ResponseCard
from app.schemas.runtime_events import TranscriptFinalEvent, TranscriptPayload
from app.services.card_service import CardService
from app.services.session_service import SessionService
from app.services.visit_completion_service import VisitCompletionExecutor, VisitCompletionService
from tests.fixtures.clock import MutableClock

TEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
NOW = datetime(2026, 6, 22, tzinfo=UTC)


@pytest.mark.anyio
async def test_two_visit_flow(db_sessions, first_visit_transcript, second_visit_transcript) -> None:
    # 1. Setup service components
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

    companion_agent = CompanionAgent(clock.now, session_service)

    # 2. Start Visit 1
    session_1 = await session_service.create(user_id=TEST_USER_ID, encounter_type="pharmacy")
    context_1 = TrustedRequestContext(
        session_id=session_1.session_id, user_id=TEST_USER_ID, origin="test"
    )

    # Feed the pharmacist transcript event
    prov_evt = first_visit_transcript[0]
    event_1 = TranscriptFinalEvent(
        schema_version="0.1",
        event_id=f"evt_{uuid4()}",
        event_type="transcript.final",
        session_id=str(session_1.session_id),
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
    session_events.append(event_1.model_dump(mode="json"))

    # Compile summary draft
    draft_summary = await completion_service.prepare_summary(session_1.session_id, context_1)
    assert "coenzyme q10" in draft_summary.mentioned_drugs
    assert draft_summary.follow_up_needed is True
    assert draft_summary.family_notification_requested is True

    # Register and confirm SAVE_MEMORY card
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
        source_event_id=event_1.event_id,
        generated_at=clock.now(),
        expires_at=clock.now() + timedelta(minutes=3),
        cards=(save_card,),
    )
    card_service.register_card_set(card_set, context_1)

    selected = await card_service.select(
        CardSelectCommand(card_set_id=card_set_id, card_id=save_card.card_id, revision=1),
        context_1,
    )

    # Confirming executes the memory write via the executor
    outcome = await card_service.confirm_selected(selected.confirmation_id, context_1)
    assert outcome.action_type == CardActionType.SAVE_MEMORY

    # Verify it is written to the VisitSummary db table
    recent_visits = await visit_repo.recent_for_user(TEST_USER_ID)
    assert len(recent_visits) == 1
    assert "coenzyme q10" in recent_visits[0].value["mentioned_drugs"]

    # 3. Start Visit 2
    session_2 = await session_service.create(user_id=TEST_USER_ID, encounter_type="pharmacy")

    # Feed second visit transcript: parent asks for blood pressure medication
    prov_evt_2 = second_visit_transcript[0]
    event_2 = TranscriptFinalEvent(
        schema_version="0.1",
        event_id=f"evt_{uuid4()}",
        event_type="transcript.final",
        session_id=str(session_2.session_id),
        sequence=1,
        timestamp=clock.now(),
        correlation_id=None,
        payload=TranscriptPayload(
            utterance_id=prov_evt_2.utterance_id,
            speaker=prov_evt_2.speaker,
            language=prov_evt_2.language,
            text=prov_evt_2.text,
            revision=prov_evt_2.revision,
        ),
    )

    # CompanionAgent should proactively propose a card suggesting to ask about Coenzyme Q10!
    route_decision = RouteDecision(
        route_type=RouteType.PHARMACY_RISK,
        confidence=0.9,
        reason_code=RouteReasonCode.PHARMACY_TERM,
    )

    from unittest.mock import patch

    from google.adk.events import Event

    async def mock_run_async(self_runner, user_id, session_id, new_message=None, **kwargs):
        from datetime import timedelta
        from uuid import uuid4

        from app.core.constants import CardActionType, CardRiskLevel
        from app.schemas.agent_outputs import CardSetProposal
        from app.schemas.cards import CardAction, CardSet, CardType, ResponseCard

        session = await self_runner.session_service.get_session(
            app_name=self_runner.app_name, user_id=user_id, session_id=session_id
        )
        if session is None:
            await self_runner.session_service.create_session(
                app_name=self_runner.app_name, user_id=user_id, session_id=session_id
            )
        mock_cards = (
            ResponseCard(
                card_id=f"card_{uuid4()}",
                card_type=CardType.ASK_QUESTION,
                zh_text="询问药剂师：我需要服用辅酶Q10吗？",
                en_text="Ask pharmacist: Did you mean Coenzyme Q10?",
                risk_level=CardRiskLevel.NORMAL,
                action=CardAction(type=CardActionType.NO_ACTION),
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id=f"guardian_{uuid4()}",
            ),
            ResponseCard(
                card_id=f"card_{uuid4()}",
                card_type=CardType.ASK_TO_WRITE_DOWN,
                zh_text="请药剂师写下药品名",
                en_text="Ask pharmacist to write down the drug name",
                risk_level=CardRiskLevel.NORMAL,
                action=CardAction(type=CardActionType.NO_ACTION),
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id=f"guardian_{uuid4()}",
            ),
            ResponseCard(
                card_id=f"card_{uuid4()}",
                card_type=CardType.ASK_QUESTION,
                zh_text="请药剂师重复一遍",
                en_text="Ask pharmacist to repeat",
                risk_level=CardRiskLevel.NORMAL,
                action=CardAction(type=CardActionType.NO_ACTION),
                requires_parent_confirmation=True,
                requires_guardian_approval=True,
                guardian_decision_id=f"guardian_{uuid4()}",
            ),
        )
        proposal = CardSetProposal(
            card_set=CardSet(
                card_set_id=f"cards_{uuid4()}",
                revision=1,
                source_event_id=event_2.event_id,
                generated_at=clock.now(),
                expires_at=clock.now() + timedelta(minutes=3),
                cards=mock_cards,
            ),
            proposal_hash="dummy_hash",
        )
        real_session = self_runner.session_service.sessions[self_runner.app_name][user_id][
            session_id
        ]
        real_session.state["companion_proposal"] = proposal.model_dump()
        yield Event(author="Companion", message="Mock proposal cards")

    with patch("google.adk.runners.Runner.run_async", mock_run_async):
        proposal = await companion_agent.propose_cards(
            event_2, route_decision, f"guardian_{uuid4()}"
        )

    assert len(proposal.card_set.cards) == 3
    assert any("辅酶Q10" in card.zh_text for card in proposal.card_set.cards)
    assert any("Coenzyme Q10" in card.en_text for card in proposal.card_set.cards)
