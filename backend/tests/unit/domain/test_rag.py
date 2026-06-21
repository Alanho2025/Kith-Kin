from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.rag import (
    RetrievalCategory,
    RetrievalRequest,
    RetrievalSnippet,
    limit_retrieval_context,
)

NOW = datetime(2026, 6, 22, tzinfo=UTC)


def snippet(number: int, *, match_count: int = 1, content: str = "fact") -> RetrievalSnippet:
    return RetrievalSnippet(
        record_id=UUID(int=number),
        record_type="medication",
        content=content,
        updated_at=NOW - timedelta(minutes=number),
        tag_match_count=match_count,
    )


def test_limits_retrieval_to_five_records_in_deterministic_order() -> None:
    records = [snippet(number) for number in range(1, 7)]

    result = limit_retrieval_context(records, max_records=5, max_chars=4000)

    assert [item.record_id.int for item in result.snippets] == [1, 2, 3, 4, 5]
    assert result.truncated is True


def test_orders_higher_tag_match_before_newer_record() -> None:
    records = [snippet(1, match_count=1), snippet(2, match_count=2)]

    result = limit_retrieval_context(records, max_records=5, max_chars=4000)

    assert [item.record_id.int for item in result.snippets] == [2, 1]


def test_truncates_last_record_to_character_budget_with_ellipsis() -> None:
    records = [snippet(1, content="abcdef")]

    result = limit_retrieval_context(records, max_records=5, max_chars=5)

    assert result.snippets[0].content == "abcd…"
    assert result.total_chars == 5
    assert result.truncated is True


def test_retrieval_request_cannot_accept_caller_identity() -> None:
    fields = RetrievalRequest.__dataclass_fields__

    assert "user_id" not in fields
    assert "session_id" not in fields
    request = RetrievalRequest(
        query="profile",
        tags=("medications",),
        category=RetrievalCategory.MEDICATIONS,
    )
    assert request.query == "profile"
