import os
import pytest
from uuid import uuid4
from datetime import datetime, UTC

from app.core.config import Settings
from app.domain.credentials import TrustedRequestContext
from app.schemas.runtime_events import TranscriptFinalEvent, TranscriptPayload
from app.schemas.agent_outputs import RouteDecision, RouteReasonCode, RouteType
from app.services.turn_orchestrator import TurnOrchestrator
from app.agents.router_agent import RouterAgent
from app.agents.guardian_agent import GuardianAgent
from app.agents.companion_agent import CompanionAgent
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.drug_knowledge_repository import DrugKnowledgeRepository
from app.services.rag_service import RagService
from app.adapters.mcp_tool_adapter import McpToolAdapter
from app.services.card_service import CardService
from app.services.visit_completion_service import VisitCompletionExecutor, VisitCompletionService
from app.repositories.confirmation_repository import InMemoryConfirmationRepository

TEST_USER_ID = os.getenv("TEST_USER_ID", "00000000-0000-4000-8000-000000000001")


@pytest.mark.skipif(
    not os.environ.get("GOOGLE_API_KEY"),
    reason="GOOGLE_API_KEY environment variable not set for live smoke tests."
)
@pytest.mark.anyio
async def test_adk_live_flow(db_sessions) -> None:
    # Set up settings with the API key from environment
    settings = Settings(google_api_key=os.environ.get("GOOGLE_API_KEY"))

    clock_now = lambda: datetime.now(UTC)
    session_id = uuid4()
    context = TrustedRequestContext(session_id=session_id, user_id=TEST_USER_ID, origin="test")

    # Repos and Services
    memory_repo = MemoryRepository(db_sessions, clock_now)
    notification_repo = NotificationRepository(db_sessions, clock_now)
    drug_knowledge_repo = DrugKnowledgeRepository(db_sessions)
    rag_service = RagService(settings, memory_repo, None)

    completion_service = VisitCompletionService(
        memory_repository=memory_repo,
        notification_repository=notification_repo,
        get_session_events=lambda sid: [],
    )
    confirmation_repository = InMemoryConfirmationRepository()
    completion_executor = VisitCompletionExecutor(completion_service, confirmation_repository)

    card_service = CardService(
        clock=clock_now,
        executor=completion_executor,
        repository=confirmation_repository,
    )

    router_agent = RouterAgent()
    guardian_agent = GuardianAgent()
    companion_agent = CompanionAgent(clock_now, None)

    def mcp_tool_adapter_factory(ctx):
        return McpToolAdapter(
            settings=settings,
            context=ctx,
            rag_service=rag_service,
            memory_repository=memory_repo,
            notification_repository=notification_repo,
            drug_knowledge_repository=drug_knowledge_repo,
        )

    orchestrator = TurnOrchestrator(
        router=router_agent,
        guardian=guardian_agent,
        companion=companion_agent,
        card_service=card_service,
        mcp_tool_adapter_factory=mcp_tool_adapter_factory,
        settings=settings,
        clock=clock_now,
    )

    # 1. Test routine conversation (should bypass Companion)
    event_routine = TranscriptFinalEvent(
        schema_version="0.1",
        event_id=f"evt_{uuid4()}",
        event_type="transcript.final",
        session_id=str(session_id),
        sequence=1,
        timestamp=clock_now(),
        correlation_id=None,
        payload=TranscriptPayload(
            utterance_id="utt_1",
            speaker="pharmacist",
            language="en",
            text="Hello, how can I help you today?",
            revision=1,
        )
    )
    outcome_routine = await orchestrator.process_final_turn(event_routine, context)
    assert outcome_routine.route.route_type == RouteType.PASSIVE_TRANSLATION
    assert outcome_routine.card_proposal is None

    # 2. Test response needed conversation (should invoke Companion LlmAgent)
    event_response = TranscriptFinalEvent(
        schema_version="0.1",
        event_id=f"evt_{uuid4()}",
        event_type="transcript.final",
        session_id=str(session_id),
        sequence=2,
        timestamp=clock_now(),
        correlation_id=None,
        payload=TranscriptPayload(
            utterance_id="utt_2",
            speaker="pharmacist",
            language="en",
            text="Do you have any known drug allergies?",
            revision=1,
        )
    )
    outcome_response = await orchestrator.process_final_turn(event_response, context)
    assert outcome_response.route.route_type == RouteType.RESPONSE_NEEDED
    assert outcome_response.card_proposal is not None
    assert outcome_response.card_review is not None
