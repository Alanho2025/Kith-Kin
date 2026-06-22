import asyncio
from typing import Protocol
from uuid import UUID


class TicketUseStore(Protocol):
    async def consume_once(self, jti: UUID) -> bool: ...


class InMemoryTicketUseStore:
    def __init__(self) -> None:
        self._used: set[UUID] = set()
        self._lock = asyncio.Lock()

    async def consume_once(self, jti: UUID) -> bool:
        async with self._lock:
            if jti in self._used:
                return False
            self._used.add(jti)
            return True
