from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI

from app.adapters.app_websocket_ticket_issuer import (
    AppWebSocketTicketIssuer,
    AppWebSocketTicketVerifier,
)
from app.adapters.fake_live_adapter import FakeLiveAdapter
from app.api.error_handlers import install_error_handlers
from app.api.routes import cards, health, live, sessions
from app.core.config import Settings
from app.repositories.session_store import InMemorySessionStore
from app.repositories.ticket_use_store import InMemoryTicketUseStore
from app.services.card_service import CardService
from app.services.live_runtime_service import LiveRuntimeService
from app.services.session_service import SessionService
from app.services.ticket_service import TicketService

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
    app = FastAPI(title="Kith&Kin API")

    session_store = InMemorySessionStore()
    ticket_use_store = InMemoryTicketUseStore()
    session_service = SessionService(session_store, clock)
    issuer = AppWebSocketTicketIssuer(resolved_settings, clock)
    verifier = AppWebSocketTicketVerifier(
        resolved_settings,
        clock,
        session_store,
        ticket_use_store,
    )
    card_service = CardService()

    app.state.settings = resolved_settings
    app.state.user_id = user_id
    app.state.session_store = session_store
    app.state.session_service = session_service
    app.state.ticket_service = TicketService(resolved_settings, session_service, issuer)
    app.state.ticket_verifier = verifier
    app.state.card_service = card_service
    app.state.live_runtime_service = LiveRuntimeService(
        card_service,
        FakeLiveAdapter(),
        clock,
    )

    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(sessions.router)
    app.include_router(cards.router)
    app.include_router(live.router)
    return app


app = create_app()
