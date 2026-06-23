from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from app.core.errors import SessionNotConnectableError
from app.repositories.session_store import SessionRecord, SessionStore
from app.repositories.visit_repository import VisitRepository


class SessionService:
    def __init__(
        self,
        store: SessionStore,
        clock: Callable[[], datetime],
        visit_repository: VisitRepository | None = None,
    ) -> None:
        self._store = store
        self._clock = clock
        self._visit_repository = visit_repository
        self.prefetch_cache: dict[UUID, list[dict[str, Any]]] = {}

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
        if self._visit_repository is not None:
            summaries = await self._visit_repository.recent_for_user(user_id, limit=5)
            self.prefetch_cache[record.session_id] = [s.value for s in summaries]
        return record

    async def require_connectable(self, session_id: UUID, user_id: UUID) -> SessionRecord:
        record = await self._store.get(session_id)
        if record is None or record.status == "ended" or record.user_id != user_id:
            raise SessionNotConnectableError
        if session_id not in self.prefetch_cache and self._visit_repository is not None:
            summaries = await self._visit_repository.recent_for_user(user_id, limit=5)
            self.prefetch_cache[session_id] = [s.value for s in summaries]
        return record

    async def end(self, session_id: UUID, user_id: UUID) -> SessionRecord:
        await self.require_connectable(session_id, user_id)
        ended = await self._store.mark_ended(session_id, self._clock())
        if ended is None:
            raise SessionNotConnectableError
        return ended
