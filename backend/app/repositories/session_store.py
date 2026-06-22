from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class SessionRecord:
    session_id: UUID
    user_id: UUID
    encounter_type: Literal["pharmacy", "gp"]
    status: Literal["created", "active", "ended"]
    created_at: datetime
    ended_at: datetime | None = None


class SessionStore(Protocol):
    async def add(self, record: SessionRecord) -> None: ...

    async def get(self, session_id: UUID) -> SessionRecord | None: ...

    async def mark_active(self, session_id: UUID) -> SessionRecord | None: ...

    async def mark_ended(self, session_id: UUID, ended_at: datetime) -> SessionRecord | None: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._records: dict[UUID, SessionRecord] = {}

    async def add(self, record: SessionRecord) -> None:
        self._records[record.session_id] = record

    async def get(self, session_id: UUID) -> SessionRecord | None:
        return self._records.get(session_id)

    async def mark_active(self, session_id: UUID) -> SessionRecord | None:
        record = self._records.get(session_id)
        if record is None or record.status == "ended":
            return record
        active = replace(record, status="active")
        self._records[session_id] = active
        return active

    async def mark_ended(self, session_id: UUID, ended_at: datetime) -> SessionRecord | None:
        record = self._records.get(session_id)
        if record is None:
            return None
        ended = replace(record, status="ended", ended_at=ended_at)
        self._records[session_id] = ended
        return ended
