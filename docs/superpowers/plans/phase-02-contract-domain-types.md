# Phase 02: Contract and Domain Types Implementation Plan

Status: implemented; checkpoint results are recorded in `docs/CODE_PLAN.md`

> **For agentic workers:** implement each domain behaviour with an observed RED before production code.

## Goal

Translate the three normative specs into typed backend/frontend contracts and pure, tested domain state machines.

## Non-Goals

No network server, database, Gemini, ADK, MCP process, browser audio, or persistence.

## Source of Truth

All `specs/*.md`, Phase 01 Settings and package boundaries.

## Previous Phase Artifacts

Backend/frontend test runners and canonical settings.

## Entry Conditions

Phase 01 checkpoint is green.

## Exit Checkpoint

Backend serialises canonical fixtures; frontend parses and maps the same fixtures; state-machine tests cover normal, invalid, stale, replay, timeout, and cancellation behaviour.

## Files

### Create

- `backend/app/core/constants.py`, `backend/app/core/errors.py`
- `backend/app/schemas/runtime_events.py`, `cards.py`, `guardian.py`, `mcp.py`, `session_schemas.py`
- `backend/app/domain/session.py`, `response_card.py`, `safety_policy.py`, `rag.py`, `credentials.py`
- `backend/tests/unit/schemas/`, `backend/tests/unit/domain/`
- `frontend/src/features/conversation/types.ts`, `constants.ts`, `mappers/runtimeEventMapper.ts`
- `frontend/src/features/conversation/runtimeEventMapper.test.ts`
- `specs/fixtures/runtime/*.json`, `specs/fixtures/cards/*.json`, `specs/fixtures/mcp/*.json`

### Modify

- No normative spec semantics.

### Test

- Backend Pydantic parsing/serialisation
- Domain state transitions
- Frontend Zod parsing and wire-to-view mapping

### Fixtures

Complete envelope/card/MCP success and failure examples.

### Migrations

None.

## Public Contracts

### Credentials

```python
@dataclass(frozen=True)
class TrustedRequestContext:
    session_id: UUID
    user_id: UUID
    origin: str

@dataclass(frozen=True)
class AppWebSocketGrant:
    encoded_ticket: SecretStr
    expires_at: datetime
    session_id: UUID
```

### RAG

Use exactly `RetrievalRequest`, `RetrievalSnippet`, `RetrievalContext`, and `RagGateway` from the master plan. `RetrievalRequest` has no identity field.

### Domain errors

- `InvalidTransitionError`
- `StaleRevisionError`
- `ConfirmationExpiredError`
- `ConfirmationReplayError`
- `UntrustedIdentityError`
- `RetrievalLimitError`

## Task 1: Runtime event union

### RED

Write schema tests for canonical events, unknown minor event, unsupported major version, invalid payload, and snake_case output.

### Verify RED

Expected import failure for `app.schemas.runtime_events`.

### GREEN

Implement a discriminated Pydantic union and central enums. Unknown supported-minor events become `UnknownRuntimeEvent`; known invalid payloads raise validation errors.

### Verify GREEN

Run backend schema tests.

### REFACTOR

Centralise only shared envelope fields and rerun.

## Task 2: Response card state machine

### RED

Test rendered→selected→awaiting_confirmation→confirmed→executing→succeeded, plus stale revision, expiry, cancel, block, and duplicate confirmation.

### Verify RED

Expected import failure for `ResponseCardStateMachine`.

### GREEN

Implement immutable state transitions. Selection never returns an executable action; only confirmed state can begin execution.

### Verify GREEN

Run focused domain tests.

### REFACTOR

Use one transition table without adding permissive fallbacks.

## Task 3: RAG truncation

### RED

Test deterministic ordering, five-record limit, 4,000-character limit, ellipsis rule, and empty result.

### GREEN

Implement a pure `limit_retrieval_context` function using Unicode code-point length and stable sorting.

## Task 4: Frontend parsing

### RED

Vitest reads complete shared fixtures and expects camelCase view models, exhaustive event narrowing, and rejection of malformed known events.

### GREEN

Implement Zod wire schemas, discriminated unions, and mapper. No `any` or raw DTO access in components.

## Checkpoint Commands

```bash
uv run --project backend pytest backend/tests/unit/schemas backend/tests/unit/domain -v
uv run --project backend ruff check backend
uv run --project backend mypy backend/app
npm --prefix frontend run test -- --run
npm --prefix frontend run lint
npm --prefix frontend run typecheck
```

## Rollback

Remove Phase 02 code and fixtures; Phase 01 remains operational.

## Stop Conditions

Any backend/frontend interpretation difference, `any`, permissive unknown payload handling, or untested transition blocks Phase 03.

## Commit Boundaries

- `feat(contracts): add typed runtime and card schemas`
- `feat(domain): add safe card and retrieval state machines`
- `feat(frontend): map canonical runtime fixtures`

## Artifacts Exposed to Next Phase

Canonical fixtures, backend DTOs, frontend DTO/view types, error codes, and pure state machines.

## Implementation Record

- Runtime parser has typed payload models for every server event and client command in `RuntimeEventType`; unknown same-major events retain envelope metadata while frontend drops untrusted payload content.
- Response-card lifecycle covers rendered, selected, awaiting confirmation, confirmed, executing, succeeded, failed, cancelled, and blocked, including stale, expiry, invalid transition, and replay errors.
- App ticket claims bind `session_id`, `user_id`, `jti`, `purpose`, `iss`, `aud`, `origin`, `iat`, `exp`, and `max_uses=1`; no Gemini grant type is present.
- RAG request contains no caller identity; limiter applies deterministic tag/update/UUID ordering, record cap, Unicode character cap, and ellipsis.
- Shared runtime/card/MCP fixtures live under `specs/fixtures/` and are parsed by backend/frontend tests.
- Migration, seed, cleanup: none. All Phase 02 behavior is pure and provider-independent.
