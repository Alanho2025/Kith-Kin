# Phase 05: PostgreSQL RAG and MCP Implementation Plan

> PostgreSQL integration tests precede every model, migration, repository, and tool implementation.

## Goal

Persist authorised profiles, sessions, confirmations, visits, notifications, and traces; expose the four canonical MCP tools; implement bounded backend RAG.

## Non-Goals

No SQLite, pgvector, clinical integration, real notification, or frontend database access.

## Source of Truth

MCP spec, master RAG contract, clean-code repository rules.

## Previous Phase Artifacts

Trusted context, session/ticket ports, domain DTOs.

## Entry Conditions

PostgreSQL dev/test containers healthy; Phase 04 green.

## Exit Checkpoint

Migrations round-trip and repository/MCP/RAG integration suites pass against PostgreSQL.

## Files

### Create

SQLAlchemy base/session/models; Alembic config/migrations; repositories; RAG service; MCP server/adapter; seed script; PostgreSQL fixtures and tests.

### Modify

Docker Compose, dependencies, session/ticket store wiring.

### Test

Repository isolation, atomic JTI consumption, tool schemas, permission tiers, timeout, bounded retrieval, trace redaction.

### Fixtures

Demo parent, Lisinopril, penicillin allergy, prior visit, deterministic record timestamps.

### Migrations

Initial schema with downgrade and clean-test-database instructions.

## Public Contracts

Repository protocols never return ORM models. `RagGateway` accepts trusted context only. MCP exposes `memory_search`, `memory_write`, `check_drug_interaction`, and `notify_family`.

## Data Flows

Search scopes by trusted user, ranks and truncates deterministically, then returns snippets. Write/notify require consumed confirmation context and idempotency. Timeout/no-result/unavailable never infer facts.

## TDD Tasks

1. Migration creates and downgrades all tables.
2. Repositories enforce user/session isolation.
3. Ticket JTI consumption is atomic.
4. RAG ordering/count/character limits and allowlisted traces.
5. Four MCP schema/result/error contracts.
6. Read-only tool filter for Companion; confirmed executor for write/external tools.
7. Seed and cleanup idempotency.

## Verification

Run migration upgrade→downgrade→upgrade, focused integration tests, then full backend suite, ruff, and mypy.

## Stop Conditions

Any SQLite usage, model-controlled identity, raw profile trace, nondeterministic truncation, or non-idempotent write blocks Phase 06.

## Commit Boundaries

- `feat(db): add pharmacy memory schema`
- `feat(rag): add bounded authorised retrieval`
- `feat(mcp): add canonical pharmacy tools`

## Next Artifacts

PostgreSQL repositories, bounded RAG, MCP adapter/server, demo seed, and persistent audit primitives.

## Exact File and Migration Manifest

- Create DB: `backend/app/db/base.py`, `session.py`, and models `user.py`, `medication.py`, `allergy.py`, `visit_summary.py`, `session.py`, `ticket_use.py`, `confirmation.py`, `notification.py`, `trace_event.py`.
- Create repositories: `user_repository.py`, `memory_repository.py`, `visit_repository.py`, `session_repository.py`, `ticket_use_repository.py`, `trace_repository.py`.
- Create services/adapters: `rag_service.py`, `mcp_tool_adapter.py`, `backend/app/mcp_servers/memory_server.py`.
- Create Alembic: `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/versions/0001_initial_schema.py`.
- Create seed: `scripts/seed_demo_data.py`; tests and fixtures under `backend/tests/integration/db`, `rag`, and `mcp`.
- Modify `docker-compose.yml`, settings dependency wiring, and Phase 04 stores to PostgreSQL implementations.

Migration `0001` creates UUID-primary-key tables with UTC timestamps, foreign keys scoped by `user_id`, unique `(issuer, jti)`, unique idempotency keys, JSONB only for validated structured values, and indexes on `(user_id, updated_at)` and `(session_id, sequence)`. It does not create SQLite files, vector extensions, or raw transcript/audio columns.

## Exact Public Signatures

```python
class MemoryRepository(Protocol):
    async def search(
        self, request: RetrievalRequest, context: TrustedRequestContext
    ) -> Sequence[RetrievalSnippet]: ...
    async def write_visit_summary(
        self, summary: VisitSummaryValue, context: TrustedRequestContext,
        *, idempotency_key: UUID
    ) -> MemoryWriteOutcome: ...

class RagService(RagGateway):
    async def retrieve(
        self, request: RetrievalRequest, context: TrustedRequestContext
    ) -> RetrievalContext: ...

class McpToolAdapter:
    async def memory_search(self, query: str, tags: tuple[str, ...]) -> ToolResult[MemorySearchData]: ...
    async def check_drug_interaction(
        self, new_drug: str, current_meds: tuple[str, ...]
    ) -> ToolResult[DrugInteractionData]: ...
```

Only confirmed-action services receive `memory_write` and `notify_family` callables. Companion receives a tool filter containing exactly `memory_search` and `check_drug_interaction`.

## Failure, Replay, Timeout, and Trace Rules

- Repository exception → `unavailable` with stable tool code; no ORM/provider text crosses the adapter.
- `asyncio.timeout(RAG_TIMEOUT_MS / 1000)` → `RAG_TIMEOUT`, no retry after deadline.
- Empty search → `no_result` with empty records; Companion treats medications/allergies as unknown.
- Result limiting is records first, Unicode characters second, using the Phase 02 stable order.
- Write/external retries reuse the original idempotency key; changed data with the same key is `IDEMPOTENCY_CONFLICT`.
- Trace fields are only `query_category`, `record_count`, `latency_ms`, `outcome`, and `truncated`; full query/profile/snippets are forbidden.

## Executable TDD Ledger

| Cycle | RED test | Expected RED | GREEN artifact |
|---|---|---|---|
| 05.1 | `test_migration.py::test_upgrade_downgrade_upgrade` | missing revision | `0001_initial_schema.py` |
| 05.2 | `test_memory_repository.py::test_user_scope_cannot_cross_context` | cross-user row returned | scoped SQLAlchemy query |
| 05.3 | `test_ticket_use_repository.py::test_concurrent_jti_consume_has_one_winner` | two winners | unique row + transaction |
| 05.4 | `test_rag_service.py::test_timeout_no_result_unavailable_never_guess` | exception/raw value | typed result mapping |
| 05.5 | `test_rag_service.py::test_limits_and_trace_are_deterministic` | over-limit/profile trace | limiter + allowlist trace |
| 05.6 | `test_memory_server.py::test_four_tool_names_and_schemas` | server missing/drift | stdio MCP server |
| 05.7 | `test_mcp_permissions.py::test_companion_cannot_call_write_or_notify` | tool visible | tool filter/executor split |
| 05.8 | `test_seed_demo_data.py::test_seed_and_cleanup_are_idempotent` | duplicate rows | deterministic seed keys |

Representative repository RED:

```python
@pytest.mark.asyncio
async def test_user_scope_cannot_cross_context(memory_repository, user_a_context, user_b_record):
    result = await memory_repository.search(
        RetrievalRequest("profile", ("medications",), RetrievalCategory.MEDICATIONS),
        user_a_context,
    )
    assert user_b_record.record_id not in {item.record_id for item in result}
```

Run PostgreSQL tests with `TEST_DATABASE_URL` from `backend/.env.example`; no test may substitute SQLite. Verify RED with the exact node ID, GREEN with the integration directory, then full pytest/ruff/mypy. Allowed refactors are query builders and unit-of-work extraction without changing transaction ownership.

## Migration, Seed, Cleanup, and Rollback Commands

```bash
docker compose up -d postgres_test
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/alembic -c backend/alembic.ini downgrade base
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head
backend/.venv/bin/python scripts/seed_demo_data.py --database-url "$TEST_DATABASE_URL"
backend/.venv/bin/python scripts/seed_demo_data.py --database-url "$TEST_DATABASE_URL" --cleanup
```

Expected output is one applied revision, clean downgrade, identical reseed counts, and zero real identifiers. Any destructive command must target the `_test` database and print the selected database name before mutation. Failure at any migration step blocks Phase 06.
