from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.db.models.medication import Medication
from app.domain.credentials import TrustedRequestContext
from app.domain.rag import RetrievalCategory, RetrievalRequest
from app.repositories.memory_repository import MemoryRepository

NOW = datetime(2026, 6, 22, tzinfo=UTC)
TEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000002")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")


async def test_user_scope_cannot_cross_context(db_sessions) -> None:
    async with db_sessions() as session:
        session.add(
            Medication(
                user_id=OTHER_USER_ID,
                name="Other parent medicine",
                dose="hidden",
                notes="must not cross user scope",
                tags=["profile", "medications"],
                updated_at=NOW,
            )
        )
        await session.commit()
    repository = MemoryRepository(db_sessions, lambda: NOW)

    result = await repository.search(
        RetrievalRequest("profile", ("medications",), RetrievalCategory.MEDICATIONS),
        TrustedRequestContext(session_id=SESSION_ID, user_id=TEST_USER_ID, origin="test"),
    )

    assert all("Other parent medicine" not in item.content for item in result)


async def test_search_orders_by_phase_policy_inputs(db_sessions) -> None:
    async with db_sessions() as session:
        for index in range(6):
            session.add(
                Medication(
                    user_id=TEST_USER_ID,
                    name=f"Medication {index}",
                    dose=None,
                    notes=None,
                    tags=["profile", "medications"] if index == 5 else ["medications"],
                    updated_at=NOW - timedelta(minutes=index),
                )
            )
        await session.commit()
    repository = MemoryRepository(db_sessions, lambda: NOW)

    result = await repository.search(
        RetrievalRequest("profile", ("profile", "medications"), RetrievalCategory.PROFILE),
        TrustedRequestContext(session_id=SESSION_ID, user_id=TEST_USER_ID, origin="test"),
    )

    assert result[0].tag_match_count >= result[1].tag_match_count
