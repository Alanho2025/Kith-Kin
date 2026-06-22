from collections.abc import Callable
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from app.core.errors import SessionNotConnectableError
from app.repositories.session_store import SessionRecord, SessionStore


class SessionService:
    def __init__(self, store: SessionStore, clock: Callable[[], datetime]) -> None:
        self._store = store
        self._clock = clock

    async def create(
        self,
        *,
        user_id: UUID,
        encounter_type: Literal["pharmacy", "gp"],
    ) -> SessionRecord:
        record = SessionRecord(
            session_id=uuid4(),
            user_id=user_id,
            encounter_type=encounter_type,
            status="created",
            created_at=self._clock(),
        )
        await self._store.add(record)
        return record

    async def require_connectable(self, session_id: UUID, user_id: UUID) -> SessionRecord:
        record = await self._store.get(session_id)
        if record is None or record.status == "ended" or record.user_id != user_id:
            raise SessionNotConnectableError
        return record

    async def end(self, session_id: UUID, user_id: UUID) -> SessionRecord:
        await self.require_connectable(session_id, user_id)
        ended = await self._store.mark_ended(session_id, self._clock())
        if ended is None:
            raise SessionNotConnectableError
        return ended
