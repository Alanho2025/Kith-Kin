# Kith&Kin (KK) - AI Agent Companion for Elderly Chinese Immigrants in Australia

## Project Overview
Kith&Kin is a real-time AI companion that helps elderly Chinese-speaking parents navigate medical encounters in Australia independently. When their adult children are at work, KK listens, faithfully translates, and helps parents respond safely during pharmacy or GP visits.

**Competition:** Google × Kaggle "AI Agents: Intensive Vibe Coding" Capstone
**Track:** Concierge Agents
**Deadline:** July 6, 2026, 11:59 PM PT
**Flagship demo:** Pharmacy visit. Hero moment = KK writes the visit outcome back to memory, then proactively recalls it on the next visit.

---

## ⚠️ Validate First (single biggest unknown)
The visual track depends on extracting `input_transcription` from the Live API **agent-mode** session and translating it. Before building anything else, confirm in AI Studio that agent mode emits a usable `input_transcription` for the foreign speaker's audio.

- **If yes:** proceed with the text-translation bypass below.
- **If no / unreliable:** fall back to the dedicated `gemini-3.5-live-translate-preview` for the visual track (accept a second stream). Do not discover this on day 8.

---

## Tech Stack
- **Python 3.10+** - backend runtime, FastAPI services, ADK agents, MCP server, scripts, and eval runner.
- **FastAPI** - backend API layer, WebSocket runtime endpoint, session management, card confirmation, and app WebSocket ticket endpoint.
- **Google Gemini LLM models** - all LLM reasoning, translation support, and agent responses must use Gemini models only.
- **Gemini Live API** - one WebSocket session per active conversation for bidirectional audio and `input_transcription`.
- **Gemini Flash** - lightweight text-to-text translation bypass for faithful English-to-Chinese visual captions.
- **Google ADK** - multi-agent orchestration for Router, Companion, and Guardian agents.
- **MCP** - tool layer through ADK `McpToolset`, with stdio transport preferred for the MVP.
- **PostgreSQL** - persistent memory, user profile, medication records, visit summaries, trace metadata, and eval trace storage.
- **SQLAlchemy or SQLModel + Alembic** - database access, repository layer, and schema migrations.
- **React + TypeScript** - frontend application and elderly-friendly conversation UI.
- **Tailwind CSS** - styling system for layout, spacing, typography, large tap targets, and responsive UI.
- **Vite** - recommended frontend build tool.
- **Pytest** - backend unit and integration tests.
- **Vitest + React Testing Library** - frontend unit and component behavior tests.
- **Custom eval runner** - agent, tool-trajectory, Guardian, translation, fallback, and UI event contract evaluation.

### Stack rules

1. Do not use SQLite for the main memory store. Use PostgreSQL.
2. Do not use Vanilla HTML/JS for the production frontend. Use React, TypeScript, and Tailwind CSS.
3. Do not use non-Gemini LLM providers unless the project owner explicitly changes this rule.
4. Do not put API keys, service credentials, database URLs, or long-lived tokens in the frontend.
5. Keep provider details behind adapters. FastAPI endpoints and React components must not call Gemini, MCP, or PostgreSQL directly.
---

## Architecture - Single Live API session + Audio-Visual split

```
User/Pharmacist audio → Live API (single WS session)
                              │
        ┌─────────────────────┼─────────────────────┐
        ↓                     ↓                     ↓
  input_transcription    model audio out      function-call / JSON
  (English text)         (KK's Chinese TTS)    (response cards)
        ↓                     ↓                     ↓
  Flash text translate   play through         render oversized
  → Chinese              speaker              confirm-cards
        ↓                (mic MUTED while
  VISUAL TRACK            playing)            VOICE/CARD TRACK
  (faithful, big text)                       (agent-powered)
```

The frontend parses **three** channels off the one WebSocket: audio, JSON cards, and `input_transcription`. The transcription channel is the easiest to forget; without it the visual track is empty.

### Key Design Decisions
1. **Single Live API connection** - not dual-stream.
2. **Text translation bypass** - a Flash call translates `input_transcription` (which is the speaker's *source-language* text, i.e. English) into Chinese. This keeps the visual track faithful and hallucination-free. **KK must never produce this translation itself.**
3. **Audio-visual split** - eyes read the faithful translation; ears hear KK's suggestions; one pipeline, two destinations.
4. **Translation triggered on Live API native endpointing** (turn-complete), not per-token. Translate one full utterance at a time to avoid UI flicker.
5. **Two-layer subtitle UI:**
   - **Top:** live English transcript (small, grey, may flicker = "system is working")
   - **Bottom:** stable Chinese (large, high-contrast, **append-only** - never rewrite already-rendered characters)

---

## Three Required Course Concepts (must show in code)

### 1. ADK Multi-Agent System
LLM-driven routing (not if-else):

- **Router Agent** - classifies each turn ("routine translation" vs "needs decision"), pulls up Companion.
- **Companion Agent** - searches memory, calls drug-interaction check, generates confirm-cards.
  - **Drug-name ASR handling:** the parent's medication list is pre-loaded into context. The model matches garbled drug names phonetically/semantically - **not via Levenshtein/string-distance** (fails on phonetic errors like "Lisinopril" → "listen to pro"). On a fuzzy hit, emit a confirm-card: `[ Confirm with pharmacist: did you mean my BP med Lisinopril? ]`.
- **Guardian Agent** - **runs on every turn as a parallel safety layer, not a Router branch.** Injection detection, PII interception, consent gating. If Router sends a turn to Companion, Guardian still inspects it concurrently.

### 2. MCP Server
One stdio server, exposing:
- `memory_search(query, tags)` - search patient profile, visit history, medication records
- `memory_write(key, value, tags)` - persist new facts after each visit
- `check_drug_interaction(new_drug, current_meds)` - flag conflicts (core to the pharmacy hero moment)
- `notify_family(summary)` - send structured visit summary to the adult child (consent-gated)

Connected via ADK's `McpToolset` with stdio transport.

**Tool-latency strategy (face-to-face = zero tolerance for dead silence):**
- **Pre-fetch:** on session start, silently run `memory_search("profile")` to warm the parent's meds/allergies into context.
- **Lazy-load:** only call `check_drug_interaction` when a drug entity is actually detected in the transcript; mask the round-trip with a short TTS filler ("KK is checking that for you…").

### 3. Security Features
- **App WebSocket tickets** - frontend uses a backend-issued, single-use, short-lived session ticket; the Gemini API key never enters the client. Gemini ephemeral tokens are reserved for a future client-direct topology and are not part of the MVP.
- **Injection detection** - Guardian scans for prompt injection and sensitive-info requests.
- **PII interception (hero moment)** - Guardian uses intent classification (regex only as backstop). If the pharmacist asks for credit card / passport / Medicare number / home address, cut the normal path and force-push `[ Privacy request - KK blocked this, tap to decline ]`.
- **Consent gating** - every response card requires explicit confirmation before TTS speaks it.
- **Redaction scope:** `[REDACTED]` applies to **logs/traces and to untrusted inbound PII** (e.g. a card number the pharmacist mentions). It does **NOT** apply to the parent's own profile - the Companion legitimately needs that health data to function.

---

## Project Structure
```text
kith-and-kin/
├── backend/
│   ├── app/
│   │   ├── main.py                         # FastAPI app factory and lifespan setup
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── sessions.py             # create session, end session
│   │   │   │   ├── live.py                 # WebSocket runtime endpoint
│   │   │   │   ├── cards.py                # card confirmation endpoint
│   │   │   │   └── health.py               # health check
│   │   │   ├── dependencies.py             # database, services, settings, request context
│   │   │   └── error_handlers.py           # stable API error mapping
│   │   ├── core/
│   │   │   ├── config.py                   # settings from environment
│   │   │   ├── constants.py                # event names, statuses, risk levels
│   │   │   ├── errors.py                   # domain and application errors
│   │   │   └── logging.py                  # redacted trace logging
│   │   ├── schemas/
│   │   │   ├── session_schemas.py          # Pydantic request and response schemas
│   │   │   ├── runtime_events.py           # WebSocket event DTOs
│   │   │   ├── cards.py                    # response card contract
│   │   │   └── guardian.py                 # Guardian warning and decision schemas
│   │   ├── domain/
│   │   │   ├── session.py                  # domain objects and invariants
│   │   │   ├── memory.py
│   │   │   ├── safety_policy.py
│   │   │   └── response_card.py
│   │   ├── services/
│   │   │   ├── session_service.py          # session workflow
│   │   │   ├── live_runtime_service.py     # single Live API session orchestration
│   │   │   ├── translation_service.py      # faithful text translation bypass
│   │   │   ├── card_service.py             # card confirmation workflow
│   │   │   └── trace_service.py            # trace events for eval and debugging
│   │   ├── agents/
│   │   │   ├── router_agent.py             # ADK text-level routing agent
│   │   │   ├── companion_agent.py          # ADK pharmacy support agent
│   │   │   ├── guardian_agent.py           # ADK safety and consent gate
│   │   │   └── prompts/                    # prompt templates and agent instructions
│   │   ├── adapters/
│   │   │   ├── gemini_live_adapter.py      # Live API session adapter
│   │   │   ├── gemini_text_adapter.py      # Gemini text model adapter
│   │   │   ├── mcp_tool_adapter.py         # MCP client boundary
│   │   │   └── notification_adapter.py     # family notification stub or provider
│   │   ├── repositories/
│   │   │   ├── user_repository.py
│   │   │   ├── memory_repository.py
│   │   │   ├── visit_repository.py
│   │   │   └── trace_repository.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py                  # database session and engine setup
│   │   │   └── models/
│   │   │       ├── user.py
│   │   │       ├── medication.py
│   │   │       ├── visit_summary.py
│   │   │       └── trace_event.py
│   │   └── mcp_servers/
│   │       └── memory_server.py            # stdio MCP server for memory and pharmacy tools
│   ├── alembic/
│   │   └── versions/
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── fixtures/
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── App.tsx
│   │   │   └── router.tsx
│   │   ├── pages/
│   │   │   ├── StartPage.tsx
│   │   │   ├── ConversationPage.tsx
│   │   │   └── VisitSummaryPage.tsx
│   │   ├── components/
│   │   │   ├── StatusBar.tsx
│   │   │   ├── TwoLayerSubtitle.tsx
│   │   │   ├── ResponseCard.tsx
│   │   │   ├── ConfirmationSheet.tsx
│   │   │   ├── GuardianWarningCard.tsx
│   │   │   └── BottomControls.tsx
│   │   ├── features/
│   │   │   └── conversation/
│   │   │       ├── hooks/
│   │   │       │   ├── useLiveConversation.ts
│   │   │       │   ├── useAudioCapture.ts
│   │   │       │   └── useCardConfirmation.ts
│   │   │       ├── api/
│   │   │       │   └── conversationApi.ts
│   │   │       ├── mappers/
│   │   │       │   └── runtimeEventMapper.ts
│   │   │       ├── types.ts
│   │   │       └── constants.ts
│   │   ├── styles/
│   │   │   └── index.css                   # Tailwind entry
│   │   └── test/
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── vite.config.ts
│
├── evals/
│   ├── EVAL_CASES.md                      # human-readable eval plan
│   ├── cases.json                         # machine-readable eval cases
│   └── run.py                             # eval runner
│
├── docs/
│   ├── ARCHITECTURE.md                    # English architecture source of truth
│   ├── UI_UX_PLAN.md                      # engineering handoff for elderly-friendly UX
│   ├── CODE_PLAN.md                       # implementation milestones and task plan
│   └── clean-code-rules.md                # mandatory clean code rules
│
├── specs/
│   ├── runtime-event-contract.md
│   ├── mcp-tool-contracts.md
│   └── response-card-contract.md
│
├── scripts/
│   ├── seed_demo_data.py                  # seed demo users, meds, allergies, visit history
│   └── check_no_secrets.py
│
├── .agents/
│   └── AGENTS.md                          # this file
├── .env.example
├── README.md
└── docker-compose.yml                     # local PostgreSQL and optional services
```

### Structure rules

1. `docs/ARCHITECTURE.md`, `docs/UI_UX_PLAN.md`, `evals/EVAL_CASES.md`, and `docs/clean-code-rules.md` are required source documents.
2. Backend endpoints stay thin. Business workflows live in services.
3. Database access lives in repositories. Do not query PostgreSQL from endpoints, agents, or React code.
4. Gemini calls live behind adapters. Do not call Gemini directly from endpoints, repositories, or React components.
5. React components render prepared UI. WebSocket, audio, and API lifecycle logic must live in hooks or API modules.
6. Shared runtime event names and statuses must be centralized in constants.
7. Documentation in `docs/` and `specs/` is part of the source of truth. Update it when contracts change.
---

## Setup & Commands

```bash
# 1. Create local environment files
cp .env.example .env
cp backend/.env.example backend/.env

# Required backend variables:
# GEMINI_API_KEY=...
# DATABASE_URL=postgresql+asyncpg://kk_user:kk_password@localhost:5432/kithkin
# ENVIRONMENT=development
# LOG_LEVEL=info
```

```bash
# 2. Start local PostgreSQL
docker compose up -d postgres
```

```bash
# 3. Backend setup
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
# 4. Database migration
cd backend
alembic upgrade head
```

```bash
# 5. Seed demo elderly profile, medications, allergies, and visit history
cd backend
python -m scripts.seed_demo_data
```

```bash
# 6. Run MCP memory server if using a separate stdio process
cd backend
python -m app.mcp_servers.memory_server
```

```bash
# 7. Run FastAPI backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# 8. Frontend setup
cd frontend
npm install
npm run dev
```

```bash
# 9. Backend quality checks
cd backend
pytest
ruff check .
mypy app
```

```bash
# 10. Frontend quality checks
cd frontend
npm run lint
npm run typecheck
npm run test
```

```bash
# 11. Agent and safety evals
python -m evals.run evals/cases.json
```

### Development order

1. Validate Gemini Live API `input_transcription` in agent mode.
2. Build the React conversation screen with mock runtime events from `docs/UI_UX_PLAN.md`.
3. Implement FastAPI session and WebSocket boundaries.
4. Connect the single Gemini Live API session from `docs/ARCHITECTURE.md`.
5. Add the translation sidecar.
6. Add Router, Companion, and Guardian.
7. Add MCP tools with PostgreSQL-backed memory.
8. Add response card confirmation.
9. Add Guardian privacy and medical safety gates.
10. Run `evals/EVAL_CASES.md` cases and capture traces.

### Command rules

1. Keep commands in this section in sync with real entrypoints.
2. Do not invent commands that do not exist in the repo after scaffolding.
3. If an entrypoint changes, update this file in the same change.
4. Do not require real production credentials for tests or evals.
5. Do not run evals against real health data.
---

## Coding Conventions

The project follows the clean-code rules in `docs/clean-code-rules.md`.

The goal is low change cost. Prefer clear, testable, safe code over clever code.

### 1. Python and FastAPI

- Use Python type hints on public functions and service boundaries.
- Use Google-style docstrings for public classes, services, adapters, and complex functions.
- Keep FastAPI endpoints thin.
- Endpoint handlers may accept request schemas, receive dependencies, call one service method, map results, and return response schemas.
- Services own business workflows.
- Repositories own PostgreSQL queries and persistence.
- Adapters own Gemini, Live API, MCP, notification, and other external provider details.
- Pydantic request schemas validate external input.
- Pydantic response schemas expose only safe public fields.
- Services must not import `Request`, `Response`, `Depends`, `HTTPException`, or FastAPI routing objects.
- Repositories must not format frontend text.
- Domain logic must not depend on provider response shapes.

### 2. Async and runtime behaviour

- Use `asyncio` for WebSocket, Gemini calls, MCP calls, PostgreSQL I/O, and notification adapters when supported.
- Do not hide blocking I/O inside async endpoints.
- Long-running tool calls must expose status events such as `checking` or `fallback`.
- Fire-and-forget tasks must have clear ownership, logging, error handling, and cancellation behaviour.
- TTS playback must trigger mic mute through explicit runtime state.

### 3. PostgreSQL and data access

- PostgreSQL is the source of truth for memory, medication records, visit summaries, trace events, and seeded demo data.
- Use migrations for schema changes.
- Do not create or modify tables manually without migration files.
- Do not return ORM models directly from endpoints.
- Do not leak database field names into frontend components.
- Transaction ownership must be clear. Multi-step workflows should be controlled by service or unit-of-work logic.
- Sensitive health and identity data must be redacted in logs.

### 4. Gemini and external service adapters

- Use Gemini models only for LLM behaviour unless this rule is explicitly changed.
- Gemini Live API access must be isolated behind `GeminiLiveAdapter`.
- Gemini text calls must be isolated behind `GeminiTextAdapter`.
- Model names must be constants or settings, not repeated magic strings.
- Do not call Gemini directly from React components, FastAPI endpoints, repositories, mappers, or Pydantic validators.
- Provider errors must be mapped into safe application errors.
- Do not expose hidden prompts, full prompts with sensitive data, provider debug output, or raw Gemini responses to the frontend.

### 5. ADK agent boundaries

- Router, Companion, and Guardian have separate responsibilities.
- Router classifies transcript events and routes the next step.
- Companion handles pharmacy reasoning, memory search, drug checks, and response card generation.
- Guardian runs on every turn as a parallel safety layer.
- Guardian is a policy gate, not a suggestion agent.
- Router and Guardian are text-level agents. They must not open their own Gemini Live API sessions.
- Agent prompts and tool contracts must be documented and versioned.
- Agent outputs must use structured schemas where possible.

### 6. MCP tool conventions

- MCP tools must have clear input schemas, output schemas, permission tiers, and failure behaviour.
- `memory_search` and `check_drug_interaction` are read-only.
- `memory_write` is a write action and needs confirmation.
- `notify_family` is an external action and needs Guardian approval plus parent confirmation.
- Do not connect unverified public MCP servers to project credentials or private data.
- Tool calls must be logged with redacted input and output for eval traces.

### 7. React and TypeScript

- TypeScript must reduce uncertainty. Avoid `any` in feature code.
- Use discriminated unions for runtime events, load states, session status, Guardian decisions, and card actions.
- React components should mostly render UI.
- Components must not own WebSocket lifecycle, audio lifecycle, API fetch logic, or business rules.
- Use custom hooks for feature behaviour, such as `useLiveConversation`, `useAudioCapture`, and `useCardConfirmation`.
- Use frontend API modules for network communication and response normalization.
- Use mappers to convert backend DTOs into UI view models.
- Do not read deeply nested raw backend responses inside page components.
- Do not store derived values as state unless there is a clear reason.

### 8. Tailwind and UI implementation

- Tailwind CSS should support consistent spacing, large text, high contrast, and large tap targets.
- Avoid repeated long class strings. Extract reusable components or constants when repetition appears for the third time.
- Do not use icon-only controls for critical actions.
- Do not make visual polish block functional UX.
- Large Chinese captions, response cards, confirmation sheets, Guardian warnings, and mic mute state are functional UI, not decoration.
- UI behaviour must follow `docs/UI_UX_PLAN.md`.

### 9. Error handling

- Expected backend errors should use shared domain or application errors.
- Unexpected errors should be handled by global error handlers.
- Frontend user-facing errors must be clear and action-based.
- Do not show raw backend errors, stack traces, provider errors, or sensitive debug output to users.
- Important failures must have visible fallback states.

### 10. Testing and evals

- Unit test pure domain logic, mappers, builders, formatters, services, and safety policies.
- Integration test FastAPI endpoints, WebSocket event flow, repositories, and MCP tool boundaries.
- Frontend tests should focus on user-visible behaviour.
- After changing any agent, tool contract, runtime event, response card, safety policy, or translation logic, update and run evals.
- A bug fix should include a regression test or eval case that would have failed before the fix.
---

## Definition of Done (validate every change)

A change is done only when it is safe, testable, and aligned with the architecture.

### Always required

- Code follows `docs/clean-code-rules.md`.
- Architecture stays aligned with `docs/ARCHITECTURE.md`.
- UI behaviour stays aligned with `docs/UI_UX_PLAN.md`.
- Eval behaviour stays aligned with `evals/EVAL_CASES.md` and `evals/cases.json`.
- Responsibilities are separated across endpoint, service, repository, adapter, agent, hook, and component layers.
- No secrets are committed.
- No API key, database URL, long-lived token, or service credential appears in frontend code.
- Backend response schemas and frontend DTOs are aligned.
- Important errors have visible recovery states.
- Logs and traces redact sensitive health, identity, payment, and family data.
- New constants are centralized instead of repeated as magic strings.
- Documentation is updated when architecture, API contracts, runtime events, eval cases, UI states, setup commands, or clean-code rules change.

### Backend validation

- `pytest` passes.
- `ruff check .` passes.
- `mypy app` passes or documented exceptions are approved.
- FastAPI endpoints remain thin.
- Services do not import FastAPI request or response objects.
- Repositories own PostgreSQL queries.
- Database schema changes include Alembic migrations.
- PostgreSQL-backed features run against local test or demo data.
- Gemini and MCP calls go through adapters.

### Frontend validation

- `npm run lint` passes.
- `npm run typecheck` passes.
- `npm run test` passes.
- Components mostly render UI and do not own business workflows.
- Hooks own one clear feature behaviour.
- API modules own fetch, response parsing, and error mapping.
- Runtime events are typed.
- No `any` is added in feature code unless justified and narrowed quickly.
- Elderly-critical UI states are visible: listening, translating, checking, needs confirmation, speaking, blocked, error, and reconnecting.

### Agent and eval validation

- After touching Router, Companion, Guardian, MCP tools, prompts, runtime event contracts, translation bypass, card schema, safety policy, or memory schema, run:
  ```bash
  python -m evals.run evals/cases.json
  ```
- Eval traces show the expected route decisions.
- Tool trajectory is correct for pharmacy, privacy, memory, and family-notification cases.
- Guardian runs on every turn.
- Guardian blocks or gates sensitive flows.
- No medical advice appears in agent output.
- The visual translation track remains faithful and separate from KK advice.

### Product flow validation

- Core loop works end-to-end:
  ```text
  audio in
  -> input_transcription
  -> faithful Chinese caption
  -> route decision
  -> Guardian check
  -> response cards
  -> parent confirmation
  -> spoken or displayed response
  -> optional memory write
  -> optional family summary
  ```
- The frontend parses audio, response cards, and `input_transcription`.
- The Chinese subtitle is stable and append-only after final utterance.
- Response cards require confirmation before TTS.
- Mic is muted during TTS playback.
- The user can choose `我自己说`.
- Family notification happens only after explicit confirmation.
- Memory write happens only after explicit confirmation.

### If a change cannot satisfy one item

Document the gap in the pull request or commit note and explain:

- what is missing
- why it is safe for now
- when it will be fixed
- which eval or test will cover it later
---

## Critical Rules (never violate)

1. **One Live API session only.**
   Use exactly one Gemini Live API session per active conversation. Router, Guardian, translation, MCP tools, and notification must not open their own Live audio sessions.

2. **Multi-agent means text-level reasoning, not multiple audio streams.**
   Companion Live Runtime owns KK's ears and mouth. Router and Guardian consume transcript events and system events.

3. **Faithful translation stays separate from agent advice.**
   The visual track is produced by the text translation bypass from `input_transcription`. KK must not rewrite, summarize, or decorate this track as if it were the pharmacist's words.

4. **KK never speaks for the parent without explicit confirmation.**
   Tapping a card must not immediately speak. The user must confirm before TTS, display-to-pharmacist, memory write, or family notification.

5. **Guardian runs on every turn.**
   Guardian is a parallel safety layer. It is not only a Router branch. It must inspect sensitive requests, proposed cards, proposed tool calls, memory writes, and family notifications.

6. **No medical advice.**
   KK can help the elderly user ask the pharmacist safe questions. KK must not diagnose, prescribe, recommend taking medicine, recommend avoiding medicine, change dosage, or stop medication.

7. **Health, identity, payment, address, and family data require consent gates.**
   Credit card, passport, Medicare number, home address, date of birth, medication history, allergies, chronic conditions, and family contact information must never be shared automatically.

8. **Frontend must never hold secrets.**
   React code must not contain Gemini API keys, database credentials, MCP credentials, long-lived tokens, hidden prompts, or provider secrets. Use backend-issued short-lived tokens only when needed.

9. **PostgreSQL access goes through repositories.**
   Do not query the database from React, FastAPI endpoints, ADK agents, Pydantic validators, or UI mappers.

10. **Gemini access goes through adapters.**
    Do not call Gemini directly from React components, endpoint handlers, repositories, or random helpers.

11. **MCP tools need permission tiers and traces.**
    Read-only tools, write tools, and external action tools must be handled differently. Write and external actions require confirmation and redacted trace logs.

12. **No silent failure in pharmacy flows.**
    If transcription, translation, memory search, drug lookup, Guardian, TTS, or notification fails, show a safe fallback. Do not guess missing medical facts.

13. **Mic must be muted while KK is speaking.**
    Half-duplex audio prevents KK from hearing its own TTS and causing a self-loop.

14. **When uncertain, ask or fall back.**
    Do not invent medication facts, allergy facts, family details, or pharmacist advice.

15. **Generated documentation is binding.**
    `docs/ARCHITECTURE.md`, `docs/UI_UX_PLAN.md`, `evals/EVAL_CASES.md`, and `docs/clean-code-rules.md` must guide implementation. If code conflicts with these documents, update the document deliberately or fix the code.

16. **AI-generated code must be reviewed.**
    Check for boundary leaks, unsafe fallbacks, invented imports, outdated APIs, missing tests, security risks, and broken API contracts before accepting it.
