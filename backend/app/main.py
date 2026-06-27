from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI

from app.adapters.app_websocket_ticket_issuer import (
    AppWebSocketTicketIssuer,
    AppWebSocketTicketVerifier,
)
from app.adapters.fake_live_adapter import FakeLiveAdapter
from app.adapters.gemini_live_adapter import GeminiLiveAdapter
from app.adapters.gemini_live_translate_adapter import GeminiLiveTranslateAdapter
from app.adapters.gemini_text_adapter import GeminiTextAdapter
from app.adapters.mcp_tool_adapter import McpToolAdapter
from app.agents.companion_agent import CompanionAgent
from app.agents.guardian_agent import GuardianAgent
from app.agents.router_agent import RouterAgent
from app.api.error_handlers import install_error_handlers
from app.api.routes import cards, health, live, sessions
from app.core.config import Settings
from app.db.session import create_engine, create_session_factory, initialize_database
from app.domain.credentials import TrustedRequestContext
from app.repositories.drug_knowledge_repository import DrugKnowledgeRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.session_repository import SQLiteSessionStore
from app.repositories.ticket_use_repository import SQLiteTicketUseStore
from app.repositories.trace_repository import TraceRepository
from app.repositories.user_repository import UserRepository
from app.repositories.visit_repository import VisitRepository
from app.services.card_service import CardService
from app.services.live_runtime_service import LiveRuntimeService
from app.services.rag_service import RagService
from app.services.runtime_command_service import RuntimeCommandService
from app.services.session_service import SessionService
from app.services.ticket_service import TicketService
from app.services.translation_service import TranslationService
from app.services.turn_orchestrator import TurnOrchestrator

DEFAULT_DEVELOPMENT_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


def utc_now() -> datetime:
    return datetime.now(UTC)


def create_app(
    *,
    settings: Settings | None = None,
    user_id: UUID = DEFAULT_DEVELOPMENT_USER_ID,
    clock: Callable[[], datetime] = utc_now,
) -> FastAPI:
    resolved_settings = settings or Settings()
    if (
        resolved_settings.environment != "test"
        and resolved_settings.google_api_key.get_secret_value()
    ):
        import os

        os.environ["GOOGLE_API_KEY"] = resolved_settings.google_api_key.get_secret_value()
        os.environ["GEMINI_API_KEY"] = resolved_settings.google_api_key.get_secret_value()
    database_url = (
        resolved_settings.test_database_url
        if resolved_settings.environment == "test"
        else resolved_settings.database_url
    )
    db_engine = create_engine(database_url)
    db_sessions = create_session_factory(db_engine)
    user_repository = UserRepository(db_sessions, clock)
    session_store = SQLiteSessionStore(db_sessions)
    ticket_use_store = SQLiteTicketUseStore(
        db_sessions,
        resolved_settings.app_ws_token_issuer,
        clock,
    )
    memory_repository = MemoryRepository(db_sessions, clock)
    drug_knowledge_repository = DrugKnowledgeRepository(db_sessions)
    trace_repository = TraceRepository(db_sessions, clock)
    notification_repository = NotificationRepository(db_sessions, clock)
    visit_repository = VisitRepository(db_sessions)
    rag_service = RagService(resolved_settings, memory_repository, trace_repository)
    gemini_live_adapter = GeminiLiveAdapter(resolved_settings)
    translation_gateway = (
        GeminiLiveTranslateAdapter(resolved_settings)
        if resolved_settings.live_translation_fallback_enabled
        else GeminiTextAdapter(resolved_settings)
    )
    translation_service = TranslationService(
        translation_gateway,
        timeout_ms=resolved_settings.translation_timeout_ms,
    )
    session_service = SessionService(session_store, clock, visit_repository)
    issuer = AppWebSocketTicketIssuer(resolved_settings, clock)
    verifier = AppWebSocketTicketVerifier(
        resolved_settings,
        clock,
        session_store,
        ticket_use_store,
    )
    from typing import Any

    from app.repositories.confirmation_repository import InMemoryConfirmationRepository
    from app.services.visit_completion_service import (
        VisitCompletionExecutor,
        VisitCompletionService,
    )

    confirmation_repository = InMemoryConfirmationRepository()

    live_runtime_service: LiveRuntimeService | None = None

    def get_session_events(sid: UUID) -> list[dict[str, Any]]:
        if live_runtime_service is None:
            return []
        return live_runtime_service._buffers.get(sid, [])

    completion_service = VisitCompletionService(
        memory_repository=memory_repository,
        notification_repository=notification_repository,
        get_session_events=get_session_events,
    )
    completion_executor = VisitCompletionExecutor(completion_service, confirmation_repository)

    card_service = CardService(
        clock=clock,
        executor=completion_executor,
        repository=confirmation_repository,
    )
    router_agent = RouterAgent()
    guardian_agent = GuardianAgent()
    companion_agent = CompanionAgent(clock, session_service)

    def mcp_tool_adapter_factory(context: TrustedRequestContext) -> McpToolAdapter:
        return McpToolAdapter(
            settings=resolved_settings,
            context=context,
            rag_service=rag_service,
            memory_repository=memory_repository,
            notification_repository=notification_repository,
            drug_knowledge_repository=drug_knowledge_repository,
        )

    turn_orchestrator = TurnOrchestrator(
        router=router_agent,
        guardian=guardian_agent,
        companion=companion_agent,
        card_service=card_service,
        mcp_tool_adapter_factory=mcp_tool_adapter_factory,
        settings=resolved_settings,
        clock=clock,
    )
    runtime_command_service = RuntimeCommandService(card_service, user_id)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        if resolved_settings.environment in ("test", "development"):
            await initialize_database(db_engine)
        await user_repository.ensure_demo_user(user_id)
        try:
            yield
        finally:
            await db_engine.dispose()

    app = FastAPI(title="Kith&Kin API", lifespan=lifespan)

    app.state.settings = resolved_settings
    app.state.user_id = user_id
    app.state.db_engine = db_engine
    app.state.db_sessions = db_sessions
    app.state.user_repository = user_repository
    app.state.session_store = session_store
    app.state.memory_repository = memory_repository
    app.state.drug_knowledge_repository = drug_knowledge_repository
    app.state.trace_repository = trace_repository
    app.state.notification_repository = notification_repository
    app.state.visit_repository = visit_repository
    app.state.rag_service = rag_service
    app.state.gemini_live_adapter = gemini_live_adapter
    app.state.translation_service = translation_service
    app.state.turn_orchestrator = turn_orchestrator
    app.state.runtime_command_service = runtime_command_service
    app.state.session_service = session_service
    app.state.ticket_service = TicketService(resolved_settings, session_service, issuer)
    app.state.ticket_verifier = verifier
    app.state.card_service = card_service
    live_runtime_service = LiveRuntimeService(
        card_service=card_service,
        fake_live=FakeLiveAdapter(),
        clock=clock,
        translation_service=translation_service,
        command_service=runtime_command_service,
        turn_orchestrator=turn_orchestrator,
        user_id=user_id,
        live_gateway=gemini_live_adapter,
        settings=resolved_settings,
        completion_service=completion_service,
    )
    session_service.register_cleanup_callback(live_runtime_service.discard_session)
    session_service.register_cleanup_callback(card_service.discard_session)
    session_service.register_cleanup_callback(completion_service.discard_session)
    app.state.live_runtime_service = live_runtime_service
    app.state.visit_completion_service = completion_service

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(cards.router)
    app.include_router(live.router)
    return app


app = create_app()
