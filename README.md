# Kith&Kin — The one who shows up when you can't

**Kith&Kin is a real-time AI companion for elderly Chinese-speaking parents who need to communicate safely at an Australian pharmacy counter.**

[![Kaggle Capstone](https://img.shields.io/badge/Kaggle-Concierge%20Agents-20BEFF)](https://kaggle.com/competitions/vibecoding-agents-capstone-project)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

---

## The problem

When an elderly parent visits a pharmacy alone, normal translation is not enough. They may need to understand the pharmacist, explain allergies or current medicines, ask safe follow-up questions, and remember what was said after the visit.

Generic translation apps translate words. They do not know whether the moment is a normal translation task, a medicine-risk task, a privacy-risk task, or a consent-gated family-notification task.

Kith&Kin fills that gap. It provides faithful Chinese translation, confirmable response cards, authorised profile recall, neutral pharmacist-stated product comparison, and confirmation-gated memory and family summary flows.

---

## What Kith&Kin does

| Capability | Current implementation |
|---|---|
| Real-time pharmacy conversation | React + FastAPI over one backend WebSocket, with backend-owned runtime events. |
| Faithful translation track | Final transcript events are translated by a dedicated translation service and rendered as large Chinese captions. Companion advice never writes into the translation track. |
| Agent safety track | Router and Guardian process final turns in parallel. Companion runs only for routes that need agent assistance and only after blocking decisions are respected. |
| Response cards | Backend-owned card sets are rendered in the UI. Selecting a card has no side effect; confirmation is required before speech, memory write, or notification. |
| Product options | `product.options.render` displays only pharmacist-stated product names, prices, uses, directions, and cautions. It does not rank or recommend products. |
| Memory and follow-up | Demo SQLite data stores authorised profile facts, medication/allergy context, visit summaries, and notification stubs. |
| Testing and evals | Backend tests, frontend tests, Playwright E2E, deterministic browser smoke path, and 24 executable eval cases. |

---

## Architecture

![Kith&Kin architecture](docs/architecture_diagram.svg)

The runtime has one audio transport and multiple text-level reasoning paths.

```text
Parent / Pharmacist
        ↓
React client
        ↓ one backend WebSocket
FastAPI LiveRuntimeService
        ↓
Gemini Live adapter / fake deterministic adapter
        ↓ final transcript events
 ┌──────────────────────────────┬──────────────────────────────┐
 │                              │                              │
TranslationService              Router + Guardian              Product option extraction
Faithful Chinese captions       Parallel safety/routing         Neutral pharmacist facts
 │                              │                              │
Frontend subtitles              Companion ADK agent             Product table
                                MCP tools
                                memory_search / memory_write
                                check_drug_interaction
                                notify_family
                                │
                                SQLite repositories
```

The key product rule is simple:

> Kith&Kin translates faithfully, helps the parent ask the pharmacist safer questions, and never makes medical decisions itself.

---

## Core components

### Frontend

- `frontend/src/pages/ConversationPage.tsx` — elderly-friendly pharmacy workspace.
- `frontend/src/components/ResponseCard.tsx` — confirmable Chinese response cards.
- `frontend/src/components/TwoLayerSubtitle.tsx` — large Chinese caption display with English context.
- `frontend/src/features/conversation/reducer.ts` — event-driven UI state machine.
- `frontend/src/features/conversation/runtime/BackendConversationRuntime.ts` — WebSocket runtime bridge.
- `frontend/e2e/` — Playwright backend and deterministic E2E tests.

### Backend

- `backend/app/main.py` — FastAPI app composition and dependency wiring.
- `backend/app/deterministic_main.py` — deterministic backend entrypoint for CI/browser smoke tests without live Gemini credentials.
- `backend/app/services/live_runtime_service.py` — WebSocket runtime, transcript/translation/card/action event emission.
- `backend/app/services/turn_orchestrator.py` — parallel Router + Guardian orchestration and gated Companion execution.
- `backend/app/services/card_service.py` — server-owned card set registration and confirmation lifecycle.
- `backend/app/services/runtime_command_service.py` — client command handling for card select/confirm/cancel and controls.
- `backend/app/adapters/mcp_tool_adapter.py` — MCP-style tool boundary for memory, drug interaction, and family notification.
- `backend/app/repositories/` — SQLite-backed repositories for memory, sessions, tickets, traces, visits, and notifications.

### Specs and evals

- `specs/runtime-event-contract.md` — canonical backend-to-frontend event contract.
- `specs/response-card-contract.md` — card lifecycle and confirmation rules.
- `specs/mcp-tool-contracts.md` — MCP tool inputs, outputs, permissions, and failure behavior.
- `evals/cases.json` — 24 architecture-derived eval cases covering translation, routing, privacy, confirmation, product options, browser trace replay, audio delivery, and speaker attribution.

---

## Safety boundaries

Kith&Kin must not:

- diagnose, prescribe, or recommend a medicine;
- decide which product is safest or best;
- infer missing allergies, medicines, doses, or medical history;
- speak for the parent without explicit confirmation;
- share sensitive health, identity, payment, or family information without a safe confirmation path;
- write memory or notify family on card selection alone.

Kith&Kin may:

- faithfully translate pharmacist speech;
- help the parent ask the pharmacist to confirm medicine names, directions, interactions, or cautions;
- show authorised profile facts for parent review;
- organize pharmacist-stated product facts into a neutral table;
- save visit summaries or notify family only after confirmed backend-owned actions.

---

## Running locally

### Prerequisites

- Python 3.11 or 3.12
- Node.js 18+
- Optional: `GOOGLE_API_KEY` in `backend/.env` for live Gemini paths

### Backend setup

```bash
cd backend
python -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/alembic upgrade head
cd ..
backend/.venv/bin/python -m scripts.seed_demo_data --database-url sqlite+aiosqlite:///backend/kithkin.db
```

### Start the backend

Live-capable FastAPI app:

```bash
cd backend
./.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Deterministic app for local browser smoke tests:

```bash
cd backend
./.venv/bin/python -m uvicorn app.deterministic_main:app --reload --port 8000
```

### Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

---

## Testing and verification

### Backend tests

```bash
cd backend
./.venv/bin/python -m pytest -q
```

### Frontend tests

```bash
cd frontend
npm run test
npm run typecheck
npm run lint
```

### Playwright E2E

```bash
cd frontend
npx playwright test
```

### Agent/eval suite

```bash
# From repository root, after backend setup
backend/.venv/bin/python -m pytest evals/test_runner.py -q
backend/.venv/bin/python -m evals.run evals/cases.json
```

Live Companion evals require `GOOGLE_API_KEY`:

```bash
GOOGLE_API_KEY="your-key" backend/.venv/bin/python -m evals.run evals/cases.json --require-live-companion
```

---

## Project structure

```text
Kith-Kin/
├── backend/
│   ├── app/
│   │   ├── adapters/        # Gemini, fake runtime, TTS, ticket, MCP adapters
│   │   ├── agents/          # Router, Guardian, Companion, Orchestrator helpers
│   │   ├── api/             # FastAPI routes and error handlers
│   │   ├── db/              # SQLAlchemy engine and ORM setup
│   │   ├── repositories/    # SQLite persistence boundaries
│   │   ├── schemas/         # Runtime, card, and agent DTOs
│   │   └── services/        # Runtime, orchestration, cards, sessions, summaries
│   └── tests/               # Backend unit and integration tests
├── frontend/
│   ├── src/
│   │   ├── components/      # UI components
│   │   ├── features/        # Conversation state, mapper, hooks, runtime bridge
│   │   └── pages/           # Start, conversation, visit summary pages
│   └── e2e/                 # Playwright browser tests
├── specs/                   # Runtime, card, and MCP contracts
├── evals/                   # 24 executable acceptance cases and runners
├── docs/                    # Architecture, product goal, UI/UX, writeup, diagram
└── scripts/                 # Demo data and repo hygiene utilities
```

---

## Competition

- **Track:** Concierge Agents
- **Repository:** `github.com/Alanho2025/Kith-Kin`
- **Submission:** Kaggle Vibe Coding Agents Capstone Project
- **License:** CC BY 4.0
