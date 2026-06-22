"""SQLite-backed session store implementation."""

from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select

from app.db.models.session import Session
from app.db.session import AsyncSessionFactory
from app.repositories.session_store import SessionRecord


class SQLiteSessionStore:
    """Persist session state through the Phase 04 store protocol."""

    def __init__(self, session_factory: AsyncSessionFactory) -> None:
        self._session_factory = session_factory

    async def add(self, record: SessionRecord) -> None:
        async with self._session_factory() as session:
            session.add(
                Session(
                    id=record.session_id,
                    user_id=record.user_id,
                    encounter_type=record.encounter_type,
                    status=record.status,
                    created_at=record.created_at,
                    ended_at=record.ended_at,
                )
            )
            await session.commit()

    async def get(self, session_id: UUID) -> SessionRecord | None:
        async with self._session_factory() as session:
            row = await session.get(Session, session_id)
            return _to_record(row) if row is not None else None

    async def mark_active(self, session_id: UUID) -> SessionRecord | None:
        async with self._session_factory() as session:
            row = await session.get(Session, session_id)
            if row is None or row.status == "ended":
                return _to_record(row) if row is not None else None
            row.status = "active"
            await session.commit()
            await session.refresh(row)
            return _to_record(row)

    async def mark_ended(self, session_id: UUID, ended_at: datetime) -> SessionRecord | None:
        async with self._session_factory() as session:
            row = await session.get(Session, session_id)
            if row is None:
                return None
            row.status = "ended"
            row.ended_at = ended_at
            await session.commit()
            await session.refresh(row)
            return _to_record(row)

    async def user_sessions(self, user_id: UUID) -> tuple[SessionRecord, ...]:
        """Return sessions for focused integration tests."""
        async with self._session_factory() as session:
            rows = (
                await session.scalars(
                    select(Session).where(Session.user_id == user_id).order_by(Session.created_at)
                )
            ).all()
            return tuple(_to_record(row) for row in rows)


def _to_record(row: Session) -> SessionRecord:
    return SessionRecord(
        session_id=row.id,
        user_id=row.user_id,
        encounter_type=cast(Literal["pharmacy", "gp"], row.encounter_type),
        status=cast(Literal["created", "active", "ended"], row.status),
        created_at=row.created_at,
        ended_at=row.ended_at,
    )
