import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import Settings
from app.domain.credentials import TrustedRequestContext
from app.domain.rag import RetrievalCategory, RetrievalRequest, RetrievalSnippet
from app.services.rag_service import RagService

NOW = datetime(2026, 6, 22, tzinfo=UTC)
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class StaticMemoryRepository:
    async def search(self, request, context):
        return tuple(
            RetrievalSnippet(
                record_id=UUID(int=index),
                record_type="medication",
                content=f"content-{index}",
                updated_at=NOW - timedelta(minutes=index),
                tag_match_count=1,
            )
            for index in range(1, 7)
        )


class SlowMemoryRepository:
    async def search(self, request, context):
        await asyncio.sleep(0.05)
        return ()


class CapturingTraceRepository:
    def __init__(self) -> None:
        self.payloads: list[dict[str, object]] = []

    async def record(self, context, *, event_type, payload):
        self.payloads.append(payload)


async def test_limits_and_trace_are_deterministic() -> None:
    traces = CapturingTraceRepository()
    service = RagService(
        Settings(environment="test", rag_max_records=5, rag_max_context_chars=4000),
        StaticMemoryRepository(),
        traces,
    )

    result = await service.retrieve(
        RetrievalRequest("profile", ("medications",), RetrievalCategory.MEDICATIONS),
        TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test"),
    )

    assert [item.record_id.int for item in result.snippets] == [1, 2, 3, 4, 5]
    assert result.truncated is True
    assert set(traces.payloads[0]) == {
        "query_category",
        "record_count",
        "latency_ms",
        "outcome",
        "truncated",
    }


async def test_timeout_no_result_unavailable_never_guess() -> None:
    service = RagService(
        Settings(environment="test", rag_timeout_ms=1),
        SlowMemoryRepository(),
    )

    result = await service.retrieve(
        RetrievalRequest("profile", ("medications",), RetrievalCategory.MEDICATIONS),
        TrustedRequestContext(session_id=SESSION_ID, user_id=USER_ID, origin="test"),
    )

    assert result.snippets == ()
    assert result.total_chars == 0
