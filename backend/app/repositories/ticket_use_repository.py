"""SQLite-backed ticket replay protection."""

from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.db.models.ticket_use import TicketUse
from app.db.session import AsyncSessionFactory


class SQLiteTicketUseStore:
    """Atomically consume app WebSocket ticket JTIs."""

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        issuer: str,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._issuer = issuer
        self._clock = clock

    async def consume_once(self, jti: UUID) -> bool:
        async with self._session_factory() as session:
            session.add(TicketUse(issuer=self._issuer, jti=jti, consumed_at=self._clock()))
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return False
            return True
