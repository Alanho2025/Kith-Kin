import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from app.repositories.ticket_use_repository import SQLiteTicketUseStore

NOW = datetime(2026, 6, 22, tzinfo=UTC)


async def test_concurrent_jti_consume_has_one_winner(db_sessions) -> None:
    store = SQLiteTicketUseStore(db_sessions, "issuer", lambda: NOW)
    jti = uuid4()

    results = await asyncio.gather(*(store.consume_once(jti) for _ in range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7
