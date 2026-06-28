import os
from datetime import UTC, datetime
from uuid import UUID

from app.adapters.mcp_tool_adapter import McpToolAdapter
from app.agents.companion_agent import (
    CompanionAgent,
    build_companion_instruction,
    load_companion_prompt_template,
    make_check_drug_interaction,
    make_memory_search,
    make_submit_response_cards,
)
from app.agents.guardian_agent import GuardianAgent
from app.agents.orchestrator_agent import OrchestratorAgent
from app.agents.router_agent import RouterAgent
from app.core.config import Settings
from app.db.base import import_models
from app.db.session import create_engine, create_session_factory
from app.domain.credentials import TrustedRequestContext

# Import all models to resolve table metadata foreign keys
import_models()

from app.repositories.drug_knowledge_repository import DrugKnowledgeRepository
from app.repositories.memory_repository import MemoryRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.trace_repository import TraceRepository
from app.services.rag_service import RagService

# Load settings and ensure API keys are in environment
settings = Settings()
if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key.get_secret_value()
    os.environ["GEMINI_API_KEY"] = settings.google_api_key.get_secret_value()

clock = lambda: datetime.now(UTC)

# Initialize database components for tools
db_engine = create_engine(settings.database_url)
db_sessions = create_session_factory(db_engine)

user_id = UUID("00000000-0000-4000-8000-000000000001")
session_id = UUID("00000000-0000-4000-8000-000000000101")
context = TrustedRequestContext(session_id=session_id, user_id=user_id, origin="cli_eval")

memory_repository = MemoryRepository(db_sessions, clock)
drug_knowledge_repository = DrugKnowledgeRepository(db_sessions)
trace_repository = TraceRepository(db_sessions, clock)
notification_repository = NotificationRepository(db_sessions, clock)
rag_service = RagService(settings, memory_repository, trace_repository)

mcp_adapter = McpToolAdapter(
    settings=settings,
    context=context,
    rag_service=rag_service,
    memory_repository=memory_repository,
    notification_repository=notification_repository,
    drug_knowledge_repository=drug_knowledge_repository,
)

# Standard instruction and tools
base_prompt = load_companion_prompt_template()
companion_instruction = build_companion_instruction(
    base_prompt=base_prompt,
    meds=["warfarin"],
    allergies=["penicillin"],
    prior_summary=None,
)

tools = [
    make_memory_search(mcp_adapter),
    make_check_drug_interaction(mcp_adapter),
    make_submit_response_cards(clock=clock),
]

router_agent = RouterAgent()
guardian_agent = GuardianAgent()
companion_agent = CompanionAgent(
    clock=clock,
    instruction=companion_instruction,
    tools=tools,
)

# Apply settings if text model exists
if settings.gemini_text_model:
    companion_agent.model = settings.gemini_text_model

# Clone router and guardian to prevent parent reuse validation errors
router_clone = router_agent.clone()
guardian_clone = guardian_agent.clone()

root_agent = OrchestratorAgent(
    router=router_clone,
    guardian=guardian_clone,
    companion=companion_agent,
    sub_agents=[router_clone, guardian_clone, companion_agent],
)
