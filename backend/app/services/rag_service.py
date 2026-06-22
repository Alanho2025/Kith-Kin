"""Bounded backend RAG service with redacted trace metadata."""

import asyncio
from time import perf_counter

from app.core.config import Settings
from app.domain.credentials import TrustedRequestContext
from app.domain.rag import RetrievalContext, RetrievalRequest, limit_retrieval_context
from app.repositories.memory_repository import MemoryRepository
from app.repositories.trace_repository import TraceRepository


class RagService:
    """Retrieve authorised memory through repositories and deterministic limits."""

    def __init__(
        self,
        settings: Settings,
        memory_repository: MemoryRepository,
        trace_repository: TraceRepository | None = None,
    ) -> None:
        self._settings = settings
        self._memory_repository = memory_repository
        self._trace_repository = trace_repository

    async def retrieve(
        self,
        request: RetrievalRequest,
        context: TrustedRequestContext,
    ) -> RetrievalContext:
        started = perf_counter()
        outcome = "success"
        truncated = False
        try:
            async with asyncio.timeout(self._settings.rag_timeout_ms / 1000):
                records = await self._memory_repository.search(request, context)
                result = limit_retrieval_context(
                    records,
                    max_records=self._settings.rag_max_records,
                    max_chars=self._settings.rag_max_context_chars,
                )
                if not result.snippets:
                    outcome = "no_result"
                truncated = result.truncated
                return result
        except TimeoutError:
            outcome = "timeout"
            return RetrievalContext(snippets=(), total_chars=0, truncated=False)
        except Exception:
            outcome = "unavailable"
            return RetrievalContext(snippets=(), total_chars=0, truncated=False)
        finally:
            record_count = 0 if outcome in {"timeout", "unavailable"} else len(
                locals().get("records", ())
            )
            await self._record_trace(
                context,
                query_category=request.category.value,
                record_count=record_count,
                latency_ms=int((perf_counter() - started) * 1000),
                outcome=outcome,
                truncated=truncated,
            )

    async def _record_trace(
        self,
        context: TrustedRequestContext,
        *,
        query_category: str,
        record_count: int,
        latency_ms: int,
        outcome: str,
        truncated: bool,
    ) -> None:
        if self._trace_repository is None:
            return
        await self._trace_repository.record(
            context,
            event_type="rag_retrieve",
            payload={
                "query_category": query_category,
                "record_count": record_count,
                "latency_ms": latency_ms,
                "outcome": outcome,
                "truncated": truncated,
            },
        )
