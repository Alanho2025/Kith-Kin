"""Backend-only retrieval contracts and deterministic context limiting."""

from collections.abc import Awaitable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.core.errors import RetrievalLimitError
from app.domain.credentials import TrustedRequestContext


class RetrievalCategory(StrEnum):
    """Safe trace categories for structured retrieval."""

    PROFILE = "profile"
    MEDICATIONS = "medications"
    ALLERGIES = "allergies"
    VISIT_SUMMARY = "visit_summary"


@dataclass(frozen=True)
class RetrievalRequest:
    """Retrieval parameters with deliberately no user identity field."""

    query: str
    tags: tuple[str, ...]
    category: RetrievalCategory


@dataclass(frozen=True)
class RetrievalSnippet:
    """One authorised, bounded memory snippet."""

    record_id: UUID
    record_type: str
    content: str
    updated_at: datetime
    tag_match_count: int


@dataclass(frozen=True)
class RetrievalContext:
    """Deterministically bounded snippets returned to a single turn."""

    snippets: tuple[RetrievalSnippet, ...]
    total_chars: int
    truncated: bool


class RagGateway(Protocol):
    """Backend-only retrieval boundary using trusted server identity."""

    def retrieve(
        self,
        request: RetrievalRequest,
        context: TrustedRequestContext,
    ) -> Awaitable[RetrievalContext]:
        """Retrieve only authorised snippets for the current turn."""
        ...


def limit_retrieval_context(
    records: Sequence[RetrievalSnippet],
    *,
    max_records: int,
    max_chars: int,
) -> RetrievalContext:
    """Sort and truncate records by the normative deterministic policy."""
    if max_records <= 0 or max_chars <= 0:
        raise RetrievalLimitError("RETRIEVAL_LIMIT_INVALID")
    ordered = sorted(
        records,
        key=lambda item: (-item.tag_match_count, -item.updated_at.timestamp(), str(item.record_id)),
    )
    selected: list[RetrievalSnippet] = []
    remaining = max_chars
    truncated = len(ordered) > max_records
    for item in ordered[:max_records]:
        if remaining <= 0:
            truncated = True
            break
        if len(item.content) <= remaining:
            selected.append(item)
            remaining -= len(item.content)
            continue
        content = "…" if remaining == 1 else f"{item.content[: remaining - 1]}…"
        selected.append(replace(item, content=content))
        remaining = 0
        truncated = True
        break
    if len(selected) < min(len(ordered), max_records):
        truncated = True
    return RetrievalContext(
        snippets=tuple(selected),
        total_chars=sum(len(item.content) for item in selected),
        truncated=truncated,
    )
