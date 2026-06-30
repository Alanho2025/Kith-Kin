"""Backend-owned MCP tool adapter and permission filters."""

import asyncio
from collections.abc import Awaitable
from typing import TypeVar
from uuid import UUID

from pydantic import ValidationError

from app.core.config import Settings
from app.core.constants import PermissionTier, ToolName
from app.core.conversation_debug import conversation_log, session_ref
from app.core.errors import IdempotencyConflictError
from app.domain.credentials import TrustedRequestContext
from app.domain.rag import RetrievalCategory, RetrievalRequest
from app.repositories.drug_knowledge_repository import DrugKnowledgeRepository
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
        drug_knowledge_repository: DrugKnowledgeRepository,
    ) -> None:
        self._settings = settings
        self._context = context
        self._rag = rag_service
        self._memory = memory_repository
        self._notifications = notification_repository
        self._drug_knowledge = drug_knowledge_repository

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
        conversation_log(
            "tool.memory_search.start",
            session=session_ref(self._context.session_id),
            origin=self._context.origin,
            query=query,
            tags=tags,
        )
        try:
            request = MemorySearchRequest(query=query, tags=tags)
        except ValidationError:
            conversation_log(
                "tool.memory_search.validation_error",
                session=session_ref(self._context.session_id),
                query=query,
                tags=tags,
            )
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
            conversation_log(
                "tool.memory_search.timeout",
                session=session_ref(self._context.session_id),
                query=request.query,
                tags=request.tags,
                timeout_ms=self._settings.rag_timeout_ms,
            )
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
        conversation_log(
            "tool.memory_search.result",
            session=session_ref(self._context.session_id),
            query=request.query,
            tags=request.tags,
            status=status.value,
            record_count=len(records),
            record_types=tuple(
                str(record.value.get("record_type", "unknown")) for record in records
            ),
        )
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
        conversation_log(
            "tool.drug_interaction.start",
            session=session_ref(self._context.session_id),
            origin=self._context.origin,
            new_drug=new_drug,
            current_med_count=len(current_meds),
        )
        try:
            request = DrugInteractionRequest(new_drug=new_drug, current_meds=current_meds)
        except ValidationError:
            conversation_log(
                "tool.drug_interaction.validation_error",
                session=session_ref(self._context.session_id),
                new_drug=new_drug,
                current_med_count=len(current_meds),
            )
            return _error(
                "TOOL_VALIDATION_ERROR",
                "Invalid drug interaction request.",
                "drug_invalid",
            )
        result = await _with_timeout(
            self._settings.drug_check_timeout_ms,
            self._check_db_interaction(request),
        )
        if result is None:
            conversation_log(
                "tool.drug_interaction.timeout",
                session=session_ref(self._context.session_id),
                new_drug=request.new_drug,
                current_med_count=len(request.current_meds),
                timeout_ms=self._settings.drug_check_timeout_ms,
            )
            return _error(
                "TOOL_TIMEOUT",
                "Drug interaction check timed out.",
                "drug_check_timeout",
                status=ToolStatus.TIMEOUT,
                retryable=True,
            )
        conversation_log(
            "tool.drug_interaction.result",
            session=session_ref(self._context.session_id),
            new_drug=request.new_drug,
            current_med_count=len(request.current_meds),
            risk_level=result.risk_level.value,
            reason_code=result.reason_code,
            matched_current_med_count=len(result.matched_current_meds),
            source_type=result.source_type,
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

    async def _check_db_interaction(
        self,
        request: DrugInteractionRequest,
    ) -> DrugInteractionData:
        new_drug_name = request.new_drug
        current_meds_names = request.current_meds

        new_drug_entity = await self._drug_knowledge.find_entity(new_drug_name)
        if not new_drug_entity:
            return DrugInteractionData(
                risk_level=DrugInteractionRisk.UNKNOWN,
                reason_code="no_demo_rule",
                matched_current_meds=(),
                source_type="unknown",
            )

        highest_risk = DrugInteractionRisk.NONE
        matched_meds = []
        has_unknown_current = False

        severity = {
            DrugInteractionRisk.NEEDS_PHARMACIST_CONFIRMATION: 3,
            DrugInteractionRisk.CAUTION: 2,
            DrugInteractionRisk.UNKNOWN: 1,
            DrugInteractionRisk.NONE: 0,
        }

        for med_name in current_meds_names:
            if not med_name.strip():
                continue
            med_entity = await self._drug_knowledge.find_entity(med_name)
            if not med_entity:
                has_unknown_current = True
                continue

            interaction = await self._drug_knowledge.check_interaction(new_drug_entity, med_entity)
            if interaction:
                risk_str = interaction["risk"].upper()
                if risk_str in ("HIGH", "MODERATE"):
                    mapped_risk = DrugInteractionRisk.NEEDS_PHARMACIST_CONFIRMATION
                elif risk_str in ("LOW", "MONITOR"):
                    mapped_risk = DrugInteractionRisk.CAUTION
                else:
                    mapped_risk = DrugInteractionRisk.NONE
            else:
                mapped_risk = DrugInteractionRisk.NONE

            if severity[mapped_risk] > severity[highest_risk]:
                highest_risk = mapped_risk
                matched_meds = [med_entity.name.capitalize()]
            elif (
                severity[mapped_risk] == severity[highest_risk]
                and mapped_risk != DrugInteractionRisk.NONE
            ):
                matched_meds.append(med_entity.name.capitalize())

        if highest_risk == DrugInteractionRisk.NONE:
            if has_unknown_current:
                return DrugInteractionData(
                    risk_level=DrugInteractionRisk.UNKNOWN,
                    reason_code="no_demo_rule",
                    matched_current_meds=(),
                    source_type="unknown",
                )
            else:
                return DrugInteractionData(
                    risk_level=DrugInteractionRisk.NONE,
                    reason_code="no_known_interaction",
                    matched_current_meds=(),
                    source_type="demo_curated_data",
                )

        reason_code = "potential_interaction_found"
        matched_meds_lower = {m.lower() for m in matched_meds}
        if new_drug_name.lower() == "ibuprofen" and "lisinopril" in matched_meds_lower:
            reason_code = "demo_ibuprofen_lisinopril_caution"
        elif any(m in matched_meds_lower for m in ("lisinopril", "warfarin")):
            reason_code = "demo_current_medicine_requires_pharmacist_check"

        return DrugInteractionData(
            risk_level=highest_risk,
            reason_code=reason_code,
            matched_current_meds=tuple(matched_meds),
            source_type="demo_curated_data",
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
