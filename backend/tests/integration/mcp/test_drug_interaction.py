"""Integration tests for database-backed drug interaction tool."""

import sys
from pathlib import Path

import pytest

from app.adapters.mcp_tool_adapter import McpToolAdapter
from app.core.config import Settings
from app.db.session import create_engine, create_session_factory
from app.domain.credentials import TrustedRequestContext
from app.repositories.drug_knowledge_repository import DrugKnowledgeRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.schemas.mcp import DrugInteractionRisk
from app.services.rag_service import RagService

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from scripts.seed_demo_data import DEMO_SESSION_ID, DEMO_USER_ID, seed  # noqa: E402


@pytest.fixture(name="db_session_factory")
async def fixture_db_session_factory(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'test_interaction.db'}"
    # Seed the test database, which runs migrations and initializes tables
    await seed(database_url, cleanup=False)
    engine = create_engine(database_url)
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


@pytest.fixture(name="mcp_adapter")
def fixture_mcp_adapter(db_session_factory):
    settings = Settings(environment="test")
    context = TrustedRequestContext(
        session_id=DEMO_SESSION_ID,
        user_id=DEMO_USER_ID,
        origin="test",
    )
    memory_repo = MemoryRepository(db_session_factory, lambda: None)
    notification_repo = NotificationRepository(db_session_factory, lambda: None)
    rag_service = RagService(settings, memory_repo, None)
    drug_knowledge_repo = DrugKnowledgeRepository(db_session_factory)

    return McpToolAdapter(
        settings=settings,
        context=context,
        rag_service=rag_service,
        memory_repository=memory_repo,
        notification_repository=notification_repo,
        drug_knowledge_repository=drug_knowledge_repo,
    )


@pytest.mark.anyio
async def test_scenario_01_ibuprofen_and_perindopril(mcp_adapter):
    # Scenario 1: Ibuprofen (NSAID) + Perindopril (ACE Inhibitor)
    result = await mcp_adapter.check_drug_interaction(
        new_drug="ibuprofen",
        current_meds=("perindopril",),
    )
    assert result.ok is True
    assert result.data.risk_level == DrugInteractionRisk.NEEDS_PHARMACIST_CONFIRMATION
    assert result.data.matched_current_meds == ("Perindopril",)


@pytest.mark.anyio
async def test_scenario_02_diclofenac_and_warfarin(mcp_adapter):
    # Scenario 2: Voltaren (contains Diclofenac, NSAID) + Warfarin (Anticoagulant)
    result = await mcp_adapter.check_drug_interaction(
        new_drug="Voltaren",
        current_meds=("warfarin",),
    )
    assert result.ok is True
    assert result.data.risk_level == DrugInteractionRisk.NEEDS_PHARMACIST_CONFIRMATION
    assert result.data.matched_current_meds == ("Warfarin",)
    assert result.data.reason_code == "demo_current_medicine_requires_pharmacist_check"


@pytest.mark.anyio
async def test_scenario_03_pseudoephedrine_and_bp_meds(mcp_adapter):
    # Scenario 3: Codral (contains Pseudoephedrine, Decongestant) + Amlodipine & Candesartan
    result = await mcp_adapter.check_drug_interaction(
        new_drug="Codral",
        current_meds=("amlodipine", "candesartan"),
    )
    assert result.ok is True
    assert result.data.risk_level == DrugInteractionRisk.NEEDS_PHARMACIST_CONFIRMATION
    assert set(result.data.matched_current_meds) == {"Amlodipine", "Candesartan"}


@pytest.mark.anyio
async def test_scenario_04_grapefruit_and_atorvastatin(mcp_adapter):
    # Scenario 4: Grapefruit (CYP3A4 Inhibitor) + Atorvastatin (Statin)
    result = await mcp_adapter.check_drug_interaction(
        new_drug="grapefruit",
        current_meds=("atorvastatin",),
    )
    assert result.ok is True
    assert result.data.risk_level == DrugInteractionRisk.CAUTION
    assert result.data.matched_current_meds == ("Atorvastatin",)


@pytest.mark.anyio
async def test_lisinopril_reconciliation(mcp_adapter):
    # User Required: check_drug_interaction(ibuprofen, [Lisinopril]) must resolve
    result = await mcp_adapter.check_drug_interaction(
        new_drug="ibuprofen",
        current_meds=("Lisinopril",),
    )
    assert result.ok is True
    assert result.data.risk_level == DrugInteractionRisk.NEEDS_PHARMACIST_CONFIRMATION
    assert result.data.matched_current_meds == ("Lisinopril",)
    assert result.data.reason_code == "demo_ibuprofen_lisinopril_caution"


@pytest.mark.anyio
async def test_no_interaction_known_drugs(mcp_adapter):
    # Metformin and Rosuvastatin do not interact
    result = await mcp_adapter.check_drug_interaction(
        new_drug="metformin",
        current_meds=("rosuvastatin",),
    )
    assert result.ok is True
    assert result.data.risk_level == DrugInteractionRisk.NONE
    assert result.data.matched_current_meds == ()
    assert result.data.reason_code == "no_known_interaction"


@pytest.mark.anyio
async def test_unknown_new_drug(mcp_adapter):
    result = await mcp_adapter.check_drug_interaction(
        new_drug="some_nonexistent_drug",
        current_meds=("lisinopril",),
    )
    assert result.ok is True
    assert result.data.risk_level == DrugInteractionRisk.UNKNOWN
    assert result.data.reason_code == "no_demo_rule"
