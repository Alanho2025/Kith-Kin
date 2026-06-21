# Kith&Kin Master Code Plan

Version: 0.1.0
Status: Active implementation roadmap
Execution mode: strict test-driven development

## Goal

Build a local-first, production-shaped pharmacy companion demo with one backend-proxied Gemini Live session, faithful visual translation, ADK Router/Companion/Guardian reasoning, PostgreSQL-backed retrieval, confirmation-gated actions, redacted traces, and a React elderly-friendly UI.

## Authority

Implementation decisions use this order:

1. `AGENTS.md`
2. `specs/runtime-event-contract.md`
3. `specs/mcp-tool-contracts.md`
4. `specs/response-card-contract.md`
5. This roadmap and its phase plans
6. Draft documents under `docs/` and `evals/`

Phase 00 must reconcile lower-authority conflicts before dependent code is accepted.

## Architecture Decisions

- React connects only to the FastAPI WebSocket. FastAPI/ADK owns Gemini Live.
- The browser receives a Kith&Kin app WebSocket ticket, never a Gemini credential.
- `LiveCredentialIssuer[TGrant]` is generic, but MVP implements only `AppWebSocketTicketIssuer` and `AppWebSocketGrant`.
- A future `GeminiEphemeralGrant` is a different type and audience; it is specified only in Phase 90.
- RAG always runs in the backend and uses structured `memory_search`; MVP does not use pgvector.
- Router and Guardian inspect every final turn concurrently. Guardian reviews proposed cards and sensitive actions again.
- Companion sees only read-only MCP tools during reasoning. Confirmed services execute write/external tools.
- The faithful Chinese track is produced only from final input transcription by the translation adapter.
- Local notification is a deterministic stub behind `NotificationGateway`.
- Cloud Run and Agent Runtime are future adapters, not MVP claims.

## TDD Law

Every production behaviour follows one independent cycle:

1. RED: add one focused test.
2. Verify RED: run it and confirm the named assertion fails because behaviour is absent.
3. GREEN: add the smallest implementation that passes.
4. Verify GREEN: run focused and related tests.
5. REFACTOR: change structure only, never behaviour.
6. Verify refactor and the phase regression suite.

Pytest must not assert nondeterministic LLM prose. Agent routing, safety, response quality, and tool trajectory use eval cases. Mocks are complete contract doubles and are permitted only at real external boundaries such as Gemini, notification, and clock.

## Public Boundaries

### HTTP and WebSocket

- `GET /api/health`
- `POST /api/sessions`
- `POST /api/sessions/{session_id}/ticket`
- `POST /api/sessions/{session_id}/end`
- `POST /api/cards/confirm` as an idempotent reconnect recovery path
- `WS /api/sessions/{session_id}/live`

The live socket remains the primary card-selection and confirmation channel. There is no HTTP eval endpoint.

### Live credential protocol

```python
TGrant = TypeVar("TGrant")

class LiveCredentialIssuer(Protocol, Generic[TGrant]):
    async def issue(
        self,
        request: CredentialIssueRequest,
        context: TrustedRequestContext,
    ) -> TGrant: ...
```

`AppWebSocketGrant` contains an encoded secret ticket, expiry, and session identifier. Claims are `session_id`, `user_id`, `jti`, `purpose`, `iss`, `aud`, `origin`, `iat`, `exp`, and `max_uses`.

Ticket close codes:

| Code | Meaning |
|---:|---|
| 4401 | Missing, malformed, invalid-signature, or expired ticket |
| 4403 | Wrong origin, audience, purpose, session, or user |
| 4409 | Replayed ticket or maximum uses exceeded |
| 4410 | Session missing or not connectable |

### RAG protocol

`RagGateway.retrieve(request, trusted_context)` accepts no caller identity. It returns at most five medication, allergy, or visit-summary snippets and at most 4,000 Unicode characters. Ordering is tag-match count descending, update time descending, record ID ascending. Truncation is deterministic and traces contain only category, record count, latency, outcome, and truncation flag.

## Phase Roadmap

| Phase | Deliverable | Blocking checkpoint |
|---:|---|---|
| 00 | Contract reconciliation and Live transcription validation | Source conflict scan clean; real validation recorded or explicitly credential-blocked |
| 01 | Repository foundation and security configuration | Hygiene/config tests, backend lint/typecheck, frontend lint/typecheck |
| 02 | Canonical domain types and state machines | Backend/frontend fixtures agree; unit suites green |
| 03 | Elderly UI on mock runtime | RTL and browser UX checkpoint |
| 04 | Session ticket and fake WebSocket runtime | Ticket abuse and reconnect integration tests |
| 05 | PostgreSQL RAG and stdio MCP | PostgreSQL-only integration and tool contract tests |
| 06 | Gemini Live and translation sidecar | Provider fixtures plus opt-in real smoke |
| 07 | ADK Router, Guardian, Companion | Deterministic orchestration tests and agent evals |
| 08 | Card confirmation and half-duplex audio | Consent, replay, and audio ordering gates |
| 09 | Visit memory, notification stub, recall | Two-visit hero integration flow |
| 10 | Security, observability, eval runner | All P0 and at least 80% P1 |
| 11 | E2E demo hardening | Clean checkout full-loop acceptance |
| 90 | Future client-direct topology migration | Inactive until runtime contract major version approval |

Each phase is specified under `docs/superpowers/plans/phase-XX-*.md`. A phase may depend only on artifacts listed by its predecessor.

## Global Stop Conditions

Stop the line when:

- a RED test passes before implementation;
- a RED test errors for setup rather than failing its intended assertion;
- a phase regression fails;
- implementation requires real health data or production credentials;
- a provider API shape differs from the sanitised fixture;
- Guardian is skipped for a final turn or sensitive action;
- a secret, raw profile, or unredacted trace reaches frontend/build output;
- a migration cannot upgrade, downgrade, and upgrade again;
- the same blocker repeats three times without a new diagnostic.

## Global Verification

```bash
uv run --project backend pytest
uv run --project backend ruff check backend
uv run --project backend mypy backend/app
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test -- --run
npm --prefix frontend run build
uv run --project backend python -m evals.run evals/cases.json
```

Final pass bar: all P0 evals, at least 80% P1, zero medical-advice violations, zero unconfirmed disclosures, zero secret exposure, and a clean-checkout local demo.

## Current Status

- Phase 00: complete with deterministic fixture PASS; authenticated Gemini validation is explicitly `blocked_missing_credentials` and remains the external D1 checkpoint.
- Phase 01: complete; dependency locks, environment examples, ignore policy, secret scanner, PostgreSQL Compose config, and quality toolchains are green.
- Phase 02: complete; typed backend contracts cover every runtime event/command, card/MCP DTOs and state machines are green, and frontend/shared fixture mapping is green.
- Phases 03–11 and 90: planned, not started.

## Phase 00–02 Verification Record

Recorded 2026-06-22:

| Check | Result |
|---|---|
| Backend unit suite | 68 passed |
| Ruff | all checks passed |
| Mypy | 19 source files, no issues |
| Frontend Vitest | 2 files, 5 tests passed |
| Frontend ESLint/typecheck/build | passed |
| Docker Compose config | valid |
| Backend lock check | 83 packages resolved, lock current |
| Secret/source/bundle scan | `secret_scan_passed` |
| Sanitised Live fixture | pass; 10/10 finals, 900 ms transcription P95, 410 ms translation P95, 0 contamination |
| Real Live provider check | `blocked_missing_credentials`; no result fabricated |

The eval runner, PostgreSQL migrations, FastAPI runtime, ADK agents, and live provider adapters belong to later phases and are not claimed by this checkpoint.
