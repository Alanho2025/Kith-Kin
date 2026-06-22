"""Backend-owned MCP tool adapter and permission filters."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar
from uuid import UUID

from pydantic import ValidationError

from app.core.config import Settings
from app.core.constants import PermissionTier, ToolName
from app.core.errors import IdempotencyConflictError
from app.domain.credentials import TrustedRequestContext
from app.domain.rag import RetrievalCategory, RetrievalRequest
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.mcp import (
    DrugInteractionData,
    DrugInteractionRequest,
    DrugInteractionRisk,
    MemoryRecord,
    MemorySearchData,
    MemorySearchRequest,
    MemoryWriteData,
    MemoryWriteRequest,
    NotifyFamilyData,
    NotifyFamilyRequest,
    ToolError,
    ToolResult,
    ToolStatus,
)
from app.services.rag_service import RagService

TOOL_PERMISSION_TIERS: dict[ToolName, PermissionTier] = {
    ToolName.MEMORY_SEARCH: PermissionTier.READ_ONLY,
    ToolName.CHECK_DRUG_INTERACTION: PermissionTier.READ_ONLY,
    ToolName.MEMORY_WRITE: PermissionTier.WRITE_LOCAL,
    ToolName.NOTIFY_FAMILY: PermissionTier.EXTERNAL_ACTION,
}

COMPANION_READ_ONLY_TOOLS = (
    ToolName.MEMORY_SEARCH.value,
    ToolName.CHECK_DRUG_INTERACTION.value,
)
TData = TypeVar("TData")


class McpToolAdapter:
    """Execute the four canonical tools from trusted backend context."""

    def __init__(
        self,
        settings: Settings,
        context: TrustedRequestContext,
        rag_service: RagService,
        memory_repository: MemoryRepository,
        notification_repository: NotificationRepository,
    ) -> None:
        self._settings = settings
        self._context = context
        self._rag = rag_service
        self._memory = memory_repository
        self._notifications = notification_repository

    @staticmethod
    def companion_tool_names() -> tuple[str, ...]:
        """Tools visible to Companion during reasoning."""
        return COMPANION_READ_ONLY_TOOLS

    @staticmethod
    def permission_tier(tool_name: ToolName) -> PermissionTier:
        """Return the stable permission tier for a canonical tool."""
        return TOOL_PERMISSION_TIERS[tool_name]

    async def memory_search(
        self,
        query: str,
        tags: tuple[str, ...],
    ) -> ToolResult[MemorySearchData]:
        try:
            request = MemorySearchRequest(query=query, tags=tags)
        except ValidationError:
            return _error(
                "TOOL_VALIDATION_ERROR",
                "Invalid memory search request.",
                "memory_invalid",
            )
        result = await _with_timeout(
            self._settings.rag_timeout_ms,
            self._rag.retrieve(
                RetrievalRequest(
                    query=request.query,
                    tags=request.tags,
                    category=_category_for(request.query, request.tags),
                ),
                self._context,
            ),
        )
        if result is None:
            return _error(
                "TOOL_TIMEOUT",
                "Memory search timed out.",
                "memory_timeout",
                status=ToolStatus.TIMEOUT,
                retryable=True,
            )
        records = tuple(
            MemoryRecord(
                record_id=str(snippet.record_id),
                key=f"{snippet.record_type}:{snippet.record_id}",
                value={"content": snippet.content, "record_type": snippet.record_type},
                tags=(snippet.record_type,),
                updated_at=snippet.updated_at,
            )
            for snippet in result.snippets
        )
        status = ToolStatus.SUCCESS if records else ToolStatus.NO_RESULT
        return ToolResult[MemorySearchData](
            ok=True,
            status=status,
            data=MemorySearchData(records=records),
            error=None,
        )

    async def check_drug_interaction(
        self,
        new_drug: str,
        current_meds: tuple[str, ...],
    ) -> ToolResult[DrugInteractionData]:
        try:
            request = DrugInteractionRequest(new_drug=new_drug, current_meds=current_meds)
        except ValidationError:
            return _error(
                "TOOL_VALIDATION_ERROR",
                "Invalid drug interaction request.",
                "drug_invalid",
            )
        result = await _with_timeout(
            self._settings.drug_check_timeout_ms,
            _check_demo_interaction(request),
        )
        if result is None:
            return _error(
                "TOOL_TIMEOUT",
                "Drug interaction check timed out.",
                "drug_check_timeout",
                status=ToolStatus.TIMEOUT,
                retryable=True,
            )
        return ToolResult[DrugInteractionData](
            ok=True,
            status=ToolStatus.SUCCESS,
            data=result,
            error=None,
        )

    async def memory_write(
        self,
        request: MemoryWriteRequest,
        *,
        idempotency_key: UUID,
    ) -> ToolResult[MemoryWriteData]:
        try:
            outcome = await _with_timeout(
                self._settings.memory_write_timeout_ms,
                self._memory.write_visit_summary(
                    request.value,
                    self._context,
                    key=request.key,
                    tags=request.tags,
                    idempotency_key=idempotency_key,
                ),
            )
        except IdempotencyConflictError:
            return _error(
                "IDEMPOTENCY_CONFLICT",
                "This confirmed memory write was already used with different data.",
                "memory_idempotency_conflict",
                status=ToolStatus.BLOCKED,
            )
        if outcome is None:
            return _error(
                "TOOL_TIMEOUT",
                "Memory write timed out.",
                "memory_write_timeout",
                status=ToolStatus.TIMEOUT,
                retryable=True,
            )
        return ToolResult[MemoryWriteData](
            ok=True,
            status=ToolStatus.SUCCESS,
            data=MemoryWriteData(
                memory_record_id=str(outcome.record_id),
                key=outcome.key,
                tags=outcome.tags,
                replayed=outcome.replayed,
            ),
            error=None,
        )

    async def notify_family(
        self,
        request: NotifyFamilyRequest,
        *,
        idempotency_key: UUID,
    ) -> ToolResult[NotifyFamilyData]:
        try:
            outcome = await _with_timeout(
                self._settings.notification_timeout_ms,
                self._notifications.send_stub(
                    request.summary,
                    self._context,
                    idempotency_key=idempotency_key,
                ),
            )
        except IdempotencyConflictError:
            return _error(
                "IDEMPOTENCY_CONFLICT",
                "This confirmed notification was already used with different data.",
                "notification_idempotency_conflict",
                status=ToolStatus.BLOCKED,
            )
        if outcome is None:
            return _error(
                "TOOL_TIMEOUT",
                "Family notification timed out.",
                "notify_timeout",
                status=ToolStatus.TIMEOUT,
                retryable=True,
            )
        return ToolResult[NotifyFamilyData](
            ok=True,
            status=ToolStatus.SUCCESS,
            data=NotifyFamilyData(
                notification_id=str(outcome.notification_id),
                delivered=outcome.delivered,
                provider=outcome.provider,
                replayed=outcome.replayed,
            ),
            error=None,
        )


def _category_for(query: str, tags: tuple[str, ...]) -> RetrievalCategory:
    lowered = {query.lower(), *(tag.lower() for tag in tags)}
    if "allergy" in lowered or "allergies" in lowered:
        return RetrievalCategory.ALLERGIES
    if "visit_summary" in lowered or "visit" in lowered:
        return RetrievalCategory.VISIT_SUMMARY
    if "medications" in lowered or "medication" in lowered:
        return RetrievalCategory.MEDICATIONS
    return RetrievalCategory.PROFILE


async def _check_demo_interaction(request: DrugInteractionRequest) -> DrugInteractionData:
    candidate = request.new_drug.lower()
    current = tuple(med for med in request.current_meds if med.strip())
    matched = tuple(med for med in current if med.lower() in {"lisinopril", "warfarin"})
    if "ibuprofen" in candidate and any(med.lower() == "lisinopril" for med in current):
        return DrugInteractionData(
            risk_level=DrugInteractionRisk.NEEDS_PHARMACIST_CONFIRMATION,
            reason_code="demo_ibuprofen_lisinopril_caution",
            matched_current_meds=("Lisinopril",),
            source_type="demo_curated_data",
        )
    if matched:
        return DrugInteractionData(
            risk_level=DrugInteractionRisk.CAUTION,
            reason_code="demo_current_medicine_requires_pharmacist_check",
            matched_current_meds=matched,
            source_type="demo_curated_data",
        )
    return DrugInteractionData(
        risk_level=DrugInteractionRisk.UNKNOWN,
        reason_code="no_demo_rule",
        matched_current_meds=(),
        source_type="unknown",
    )


async def _with_timeout(
    timeout_ms: int,
    awaitable: Awaitable[TData],
) -> TData | None:
    try:
        async with asyncio.timeout(timeout_ms / 1000):
            return await awaitable
    except TimeoutError:
        return None


def _error(
    code: str,
    message: str,
    fallback_code: str,
    *,
    status: ToolStatus = ToolStatus.VALIDATION_ERROR,
    retryable: bool = False,
) -> ToolResult[TData]:
    return ToolResult[TData](
        ok=False,
        status=status,
        data=None,
        error=ToolError(
            code=code,
            message=message,
            retryable=retryable,
            fallback_code=fallback_code,
        ),
    )
