# Align README, writeup, and architecture diagram with current Kith&Kin code

Updated: 2026-06-30T00:13:33.412Z
Workspace: /Users/heminghan/Kith-Kin
Target agent: Codex (codex)

## Plan

# Task
Align `README.md`, `docs/writeup_draft.md`, and `docs/architecture_diagram.svg` with the current codebase. Do not touch application code.

# Important current-code facts to reflect
- Backend app is FastAPI in `backend/app/main.py`.
- Deterministic CI/browser entrypoint exists at `backend/app/deterministic_main.py`.
- Frontend is React 19 + TypeScript + Vite + Tailwind.
- Backend dependency range is Python `>=3.11,<3.13` in `backend/pyproject.toml`.
- Runtime contract is `specs/runtime-event-contract.md` and includes `product.options.render`.
- `evals/cases.json` has 24 cases, not 7.
- Router and Guardian process final turns in parallel; Guardian is not a Router branch.
- Companion is gated after Guardian block decisions and skipped for passive/privacy/fallback paths.
- `card.confirmed` means accepted confirmation, not speech delivered. TTS lifecycle is driven by `audio.speaking`.
- Response card selection has zero side effects; backend-owned confirmation is required.
- Product options are neutral pharmacist-stated facts only; no AI ranking/recommendation.
- Current reducer already handles translation append, product options, `card.confirmed -> checking`, `audio.speaking -> speaking`, terminal tool/action phases, and `summary.render -> needs_confirmation`.
- Do not claim all evals pass unless verified freshly. Say the repo contains 24 executable eval cases.

# Replace `README.md` with this content
```md
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
```

# Replace `docs/writeup_draft.md` with this content
```md
# Kith&Kin: The One Who Shows Up When You Can't

**Track:** Concierge Agents  
**Team:** Kith&Kin

---

## The Problem

Every immigrant family knows this moment: your parent is alone at a pharmacy counter while you are at work. They may not fully understand the pharmacist, may not know how to explain allergies or current medications in English, and may leave without a clear record of what was said.

A normal translation app helps with words, but the pharmacy counter is not just a word-by-word translation problem. The parent needs faithful translation, safe response options, privacy protection, memory of previous visits, and a way to involve family only after consent.

Kith&Kin is built for that gap. It is a real-time AI companion for elderly Chinese-speaking parents. It helps them understand the pharmacist, choose safe pharmacist-facing questions, review sensitive information before sharing it, and keep a structured summary of the visit.

---

## Why an Agent?

This problem needs an agent because the system must react differently depending on the situation.

If the pharmacist says something routine, Kith&Kin should simply translate it faithfully. If the pharmacist asks about allergies or current medicines, Kith&Kin should retrieve only authorised context and ask the parent before sharing it. If the pharmacist asks for payment or identity details, Kith&Kin should treat it as a privacy-sensitive moment. If the pharmacist provides several product options, Kith&Kin should organize only the pharmacist-stated facts without ranking or recommending them.

These behaviours require state, routing, tools, confirmation, and safety gates. That is why Kith&Kin is an agentic system rather than a translation-only app.

---

## Architecture

![Kith&Kin architecture](architecture_diagram.svg)

The current implementation uses a React frontend, a FastAPI backend, a single backend WebSocket runtime, Google Gemini adapters, ADK-style agent orchestration, MCP-style tools, and SQLite-backed repositories.

The architecture separates two tracks from the same conversation:

1. **Faithful translation track.** Final transcript events are passed to the `TranslationService`. The frontend renders large Chinese captions. Agent advice, risk hints, and response cards are not allowed to enter this translation field.

2. **Safety and action track.** Router and Guardian process final turns in parallel. Router classifies the turn, while Guardian checks privacy, medical, and safety boundaries. If a turn is blocked, Companion does not continue. If the turn needs support, Companion can use bounded tools and propose response cards.

3. **Tool and persistence layer.** The MCP-style adapter exposes `memory_search`, `memory_write`, `check_drug_interaction`, and `notify_family`. SQLite repositories store demo-safe profile, memory, session, ticket, trace, visit, and notification data.

The core invariant is:

> One real-time conversation runtime, separate faithful translation, backend-owned actions, explicit confirmation, and no medical decision-making by the AI.

---

## Three Course Concepts

### 1. ADK multi-agent orchestration

Kith&Kin uses separate agent responsibilities instead of one all-powerful chatbot.

- **Router** classifies the final turn into paths such as passive translation, pharmacy risk, privacy risk, response needed, family action, or fallback.
- **Guardian** reviews final turns and proposed actions for privacy, medical safety, consent, and prompt-injection risks.
- **Companion** runs only when a safe route needs agent assistance. It can search authorised memory, request a deterministic drug interaction check, and propose response cards.

The important design point is that Guardian is not just a Router branch. Router and Guardian process final turns in parallel, and blocking decisions prevent unsafe continuation. This matches the runtime contract and the current `TurnOrchestrator` implementation.

### 2. MCP-style tools

The Companion does not invent medical or profile facts. It uses bounded tools through the backend tool adapter.

| Tool | Purpose | Safety rule |
|---|---|---|
| `memory_search` | Reads authorised profile, allergy, medication, and visit-summary snippets. | Read-only. Missing data means unknown. |
| `check_drug_interaction` | Checks curated demo drug-interaction facts after a concrete drug name is detected. | Produces pharmacist-confirmation prompts, not medical instructions. |
| `memory_write` | Saves a reviewed visit summary. | Requires confirmed backend-owned action. |
| `notify_family` | Records or sends a family notification through the notification adapter. | Requires confirmed backend-owned action. |

This keeps external capabilities scoped and auditable.

### 3. Security and human confirmation

Kith&Kin is designed around human-in-the-loop control.

Selecting a response card has zero side effects. The backend must issue and validate a confirmation ID before speech, memory write, or family notification. The frontend sends identifiers, not executable action text or tool arguments.

The system also separates card confirmation from audio delivery. `card.confirmed` means the backend accepted the confirmation. The actual speaking lifecycle is represented by `audio.muted`, `audio.speaking`, binary audio frames, and completion or failure events.

---

## Product Experience

The frontend is designed as a pharmacy conversation workspace for elderly users.

The main screen shows large Chinese captions, a product-options table when the pharmacist gives multiple options, simple response cards, and an explicit confirmation panel before KK speaks. The right-side conversation log keeps Chinese primary and English secondary for context. There are also control paths such as self-speak, repeat, and please-wait.

For product comparison, Kith&Kin does not recommend. It only displays pharmacist-stated facts such as product name, price, use, directions, and cautions. This is important because the pharmacist remains the medical authority.

---

## Demo Flow

A typical demo can show the following sequence:

1. The pharmacist speaks in English.
2. Kith&Kin shows a faithful Chinese translation.
3. Router and Guardian process the final turn.
4. If the pharmacist asks about a medicine or allergy, Companion retrieves authorised context or asks for clarification.
5. Kith&Kin renders response cards in Chinese.
6. The parent selects a card.
7. The parent confirms before KK speaks or performs any action.
8. If the pharmacist provides several products, Kith&Kin renders a neutral product table based only on pharmacist-stated facts.
9. At the end, Kith&Kin shows a structured visit summary for review before memory save or family notification.

---

## Evaluation

The repo now contains **24 executable eval cases** in `evals/cases.json`. These cases are derived from the architecture and runtime contracts.

They cover:

- faithful translation without advice;
- medicine-risk routing;
- allergy and profile-context confirmation;
- credit-card and prompt-injection blocking;
- response-card selection with zero side effects;
- duplicate confirmation idempotency;
- half-duplex audio ordering;
- translation timeout fallback;
- memory write and family notification after confirmation only;
- cross-session recall;
- redacted privacy traces;
- pharmacist-stated product option rendering;
- overseas medicine similarity without guessing;
- browser trace replay for conversation-log purity, summary, audio delivery, and speaker attribution.

The eval suite matters because a demo can appear correct while still violating a hidden safety boundary. The evals check both final output and the event/tool trajectory.

---

## Project Journey

The project moved from a high-level pharmacy assistant idea into a contract-driven implementation.

The team first defined the product goal and safety boundaries: faithful translation, no medical advice, no automatic sensitive disclosure, and confirmation before outward actions. Then the team built runtime contracts for events, response cards, and MCP tools. The implementation followed those contracts through a FastAPI backend, React frontend, SQLite persistence layer, ADK-style agent orchestration, and deterministic tests.

A key learning was that product-grade vibe coding is not about generating more code. It is about keeping specs, code, tests, and evals aligned. In Kith&Kin, the important engineering work is the state machine: every visible UI state must correspond to a real backend event, not a frontend guess.

---

## Repository

`github.com/Alanho2025/Kith-Kin`

The repository includes the backend, frontend, runtime contracts, eval suite, Playwright E2E tests, architecture documents, product goal, and demo writeup.
```

# Replace `docs/architecture_diagram.svg` with this content
```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 860" role="img" aria-labelledby="title desc" font-family="Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif">
  <title id="title">Kith&amp;Kin current implementation architecture</title>
  <desc id="desc">A single WebSocket pharmacy conversation runtime with React frontend, FastAPI backend, Gemini Live or deterministic adapter, faithful translation, parallel Router and Guardian agents, gated Companion agent, MCP-style tools, SQLite repositories, confirmation-gated actions, and eval observability.</desc>
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#334155"/>
    </marker>
    <marker id="arrow-blue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#2563eb"/>
    </marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#16a34a"/>
    </marker>
    <marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#dc2626"/>
    </marker>
    <marker id="arrow-amber" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#d97706"/>
    </marker>
    <linearGradient id="header" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="55%" stop-color="#1e3a8a"/>
      <stop offset="100%" stop-color="#0f766e"/>
    </linearGradient>
    <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="3" stdDeviation="4" flood-color="#0f172a" flood-opacity="0.14"/>
    </filter>
    <style>
      .panel { filter: url(#shadow); }
      .label { fill: #0f172a; font-weight: 700; font-size: 15px; }
      .small { fill: #475569; font-size: 12px; }
      .tiny { fill: #64748b; font-size: 10px; }
      .tag { fill: #334155; font-weight: 700; font-size: 10px; }
      .mono { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 11px; fill: #334155; }
    </style>
  </defs>

  <rect width="1200" height="860" rx="20" fill="#f8fafc"/>
  <rect x="0" y="0" width="1200" height="74" rx="20" fill="url(#header)"/>
  <rect x="0" y="44" width="1200" height="30" fill="url(#header)"/>
  <text x="600" y="31" text-anchor="middle" fill="#ffffff" font-size="21" font-weight="800">Kith&amp;Kin Architecture</text>
  <text x="600" y="55" text-anchor="middle" fill="#dbeafe" font-size="13">Current code: React + FastAPI + one backend WebSocket + parallel Router/Guardian + gated Companion + MCP-style tools</text>

  <!-- Users and client -->
  <rect x="36" y="108" width="210" height="96" rx="16" fill="#ecfeff" stroke="#0891b2" stroke-width="2" class="panel"/>
  <text x="141" y="137" text-anchor="middle" class="label" fill="#155e75">Parent + Pharmacist</text>
  <text x="141" y="159" text-anchor="middle" class="small">Speech, touch, speaker</text>
  <text x="141" y="180" text-anchor="middle" class="tiny">Elderly-friendly pharmacy counter</text>

  <rect x="306" y="104" width="270" height="104" rx="16" fill="#ffffff" stroke="#14b8a6" stroke-width="2" class="panel"/>
  <text x="441" y="132" text-anchor="middle" class="label">React Client</text>
  <text x="441" y="154" text-anchor="middle" class="small">ConversationPage + reducer</text>
  <text x="441" y="174" text-anchor="middle" class="tiny">Large Chinese captions · product table · cards</text>
  <rect x="340" y="184" width="202" height="18" rx="9" fill="#ccfbf1"/>
  <text x="441" y="197" text-anchor="middle" class="tag" fill="#0f766e">No Gemini key in browser</text>

  <line x1="246" y1="156" x2="306" y2="156" stroke="#334155" stroke-width="2.2" marker-end="url(#arrow)"/>
  <text x="276" y="145" text-anchor="middle" class="tiny">mic + UI</text>

  <!-- Backend runtime -->
  <rect x="650" y="94" width="500" height="128" rx="18" fill="#eef2ff" stroke="#4f46e5" stroke-width="2.5" class="panel"/>
  <text x="900" y="124" text-anchor="middle" class="label" fill="#312e81">FastAPI Backend Runtime</text>
  <text x="900" y="147" text-anchor="middle" class="small">LiveRuntimeService · RuntimeCommandService · CardService</text>
  <text x="900" y="169" text-anchor="middle" class="tiny">One backend WebSocket per conversation</text>
  <text x="900" y="190" text-anchor="middle" class="mono">session.ready · transcript.final · translation.final · cards.render · product.options.render</text>

  <line x1="576" y1="156" x2="650" y2="156" stroke="#2563eb" stroke-width="2.4" marker-end="url(#arrow-blue)"/>
  <text x="613" y="144" text-anchor="middle" class="tiny" fill="#2563eb">one WS</text>

  <!-- Live provider -->
  <rect x="715" y="258" width="370" height="78" rx="14" fill="#f1f5f9" stroke="#64748b" stroke-width="2" class="panel"/>
  <text x="900" y="285" text-anchor="middle" class="label">Gemini Live Adapter / Fake Adapter</text>
  <text x="900" y="307" text-anchor="middle" class="small">Live path for demo · deterministic path for CI/browser smoke</text>
  <text x="900" y="326" text-anchor="middle" class="tiny">Provider payloads normalized before React</text>

  <line x1="900" y1="222" x2="900" y2="258" stroke="#334155" stroke-width="2" marker-end="url(#arrow)"/>
  <text x="942" y="244" class="tiny">audio + provider events</text>

  <!-- Split label -->
  <rect x="70" y="260" width="420" height="44" rx="12" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>
  <text x="280" y="286" text-anchor="middle" class="small" font-weight="700">Final transcript events split into independent product tracks</text>

  <!-- Translation track -->
  <rect x="44" y="350" width="260" height="168" rx="18" fill="#f0fdf4" stroke="#16a34a" stroke-width="2.5" class="panel"/>
  <text x="174" y="379" text-anchor="middle" class="label" fill="#166534">Faithful Translation Track</text>
  <text x="174" y="405" text-anchor="middle" class="small">TranslationService</text>
  <text x="174" y="426" text-anchor="middle" class="tiny">GeminiTextAdapter or live fallback</text>
  <line x1="84" y1="444" x2="264" y2="444" stroke="#bbf7d0" stroke-width="1"/>
  <text x="174" y="468" text-anchor="middle" class="small">Rules</text>
  <text x="174" y="488" text-anchor="middle" class="tiny">Only from transcript.final</text>
  <text x="174" y="505" text-anchor="middle" class="tiny">No advice inside translated_text</text>

  <line x1="715" y1="336" x2="304" y2="402" stroke="#16a34a" stroke-width="2.4" marker-end="url(#arrow-green)"/>
  <text x="495" y="354" text-anchor="middle" class="tiny" fill="#16a34a">translation.pending / translation.final</text>

  <!-- Agent orchestration -->
  <rect x="354" y="350" width="440" height="282" rx="20" fill="#eff6ff" stroke="#2563eb" stroke-width="2.5" class="panel"/>
  <text x="574" y="379" text-anchor="middle" class="label" fill="#1d4ed8">ADK Text-Level Orchestration</text>
  <text x="574" y="401" text-anchor="middle" class="small">TurnOrchestrator processes each final turn</text>

  <rect x="386" y="426" width="160" height="72" rx="14" fill="#ffffff" stroke="#60a5fa" stroke-width="2"/>
  <text x="466" y="453" text-anchor="middle" class="label" fill="#1d4ed8">Router</text>
  <text x="466" y="475" text-anchor="middle" class="tiny">route.decision</text>
  <text x="466" y="491" text-anchor="middle" class="tiny">passive / pharmacy / privacy</text>

  <rect x="602" y="426" width="160" height="72" rx="14" fill="#fff1f2" stroke="#dc2626" stroke-width="2"/>
  <text x="682" y="453" text-anchor="middle" class="label" fill="#b91c1c">Guardian</text>
  <text x="682" y="475" text-anchor="middle" class="tiny">parallel policy gate</text>
  <text x="682" y="491" text-anchor="middle" class="tiny">block / confirm / allow</text>

  <line x1="574" y1="416" x2="466" y2="426" stroke="#2563eb" stroke-width="2" marker-end="url(#arrow-blue)"/>
  <line x1="574" y1="416" x2="682" y2="426" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow-red)"/>
  <text x="574" y="420" text-anchor="middle" class="tiny" fill="#334155">parallel</text>

  <rect x="462" y="542" width="224" height="76" rx="14" fill="#ffffff" stroke="#2563eb" stroke-width="2"/>
  <text x="574" y="570" text-anchor="middle" class="label" fill="#1d4ed8">Companion LlmAgent</text>
  <text x="574" y="592" text-anchor="middle" class="tiny">Runs only when route needs help</text>
  <text x="574" y="609" text-anchor="middle" class="tiny">Proposes cards, not medical decisions</text>

  <line x1="466" y1="498" x2="520" y2="542" stroke="#2563eb" stroke-width="2" marker-end="url(#arrow-blue)"/>
  <line x1="682" y1="498" x2="628" y2="542" stroke="#dc2626" stroke-width="2" marker-end="url(#arrow-red)"/>
  <text x="574" y="526" text-anchor="middle" class="tiny">blocked turns skip Companion</text>

  <line x1="715" y1="336" x2="574" y2="350" stroke="#2563eb" stroke-width="2.4" marker-end="url(#arrow-blue)"/>
  <text x="628" y="336" text-anchor="middle" class="tiny" fill="#2563eb">transcript.final</text>

  <!-- Product options -->
  <rect x="842" y="370" width="302" height="146" rx="18" fill="#fffbeb" stroke="#d97706" stroke-width="2.5" class="panel"/>
  <text x="993" y="399" text-anchor="middle" class="label" fill="#92400e">Product Options Extractor</text>
  <text x="993" y="424" text-anchor="middle" class="small">`product.options.render`</text>
  <text x="993" y="447" text-anchor="middle" class="tiny">Only pharmacist-stated facts</text>
  <text x="993" y="465" text-anchor="middle" class="tiny">name · price · use · directions · cautions</text>
  <rect x="884" y="482" width="218" height="20" rx="10" fill="#fef3c7"/>
  <text x="993" y="496" text-anchor="middle" class="tag" fill="#92400e">No ranking, recommendation, or suitability</text>

  <line x1="940" y1="336" x2="980" y2="370" stroke="#d97706" stroke-width="2.4" marker-end="url(#arrow-amber)"/>

  <!-- Tools and storage -->
  <rect x="848" y="564" width="296" height="170" rx="18" fill="#ffffff" stroke="#0f766e" stroke-width="2.5" class="panel"/>
  <text x="996" y="594" text-anchor="middle" class="label" fill="#0f766e">MCP-Style Tool Boundary</text>
  <text x="996" y="618" text-anchor="middle" class="mono">memory_search</text>
  <text x="996" y="638" text-anchor="middle" class="mono">check_drug_interaction</text>
  <text x="996" y="658" text-anchor="middle" class="mono">memory_write</text>
  <text x="996" y="678" text-anchor="middle" class="mono">notify_family</text>
  <rect x="882" y="700" width="228" height="20" rx="10" fill="#ccfbf1"/>
  <text x="996" y="714" text-anchor="middle" class="tag" fill="#0f766e">server-derived context + audit boundary</text>

  <line x1="686" y1="580" x2="848" y2="638" stroke="#0f766e" stroke-width="2.2" marker-end="url(#arrow)"/>
  <text x="766" y="592" text-anchor="middle" class="tiny" fill="#0f766e">bounded tools</text>

  <rect x="848" y="770" width="296" height="50" rx="14" fill="#f1f5f9" stroke="#64748b" stroke-width="2"/>
  <text x="996" y="800" text-anchor="middle" class="label">SQLite Repositories</text>
  <text x="996" y="815" text-anchor="middle" class="tiny">memory · sessions · tickets · traces · visits · notifications</text>
  <line x1="996" y1="734" x2="996" y2="770" stroke="#334155" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- UI outputs -->
  <rect x="44" y="680" width="748" height="140" rx="20" fill="#ffffff" stroke="#0f172a" stroke-width="2.5" class="panel"/>
  <text x="418" y="709" text-anchor="middle" class="label">Frontend User Experience</text>

  <rect x="70" y="732" width="140" height="50" rx="12" fill="#f0fdf4" stroke="#16a34a" stroke-width="1.5"/>
  <text x="140" y="754" text-anchor="middle" class="tag" fill="#166534">Large Chinese</text>
  <text x="140" y="771" text-anchor="middle" class="tiny">faithful captions</text>

  <rect x="230" y="732" width="140" height="50" rx="12" fill="#fffbeb" stroke="#d97706" stroke-width="1.5"/>
  <text x="300" y="754" text-anchor="middle" class="tag" fill="#92400e">Product table</text>
  <text x="300" y="771" text-anchor="middle" class="tiny">pharmacist facts</text>

  <rect x="390" y="732" width="140" height="50" rx="12" fill="#eff6ff" stroke="#2563eb" stroke-width="1.5"/>
  <text x="460" y="754" text-anchor="middle" class="tag" fill="#1d4ed8">Response cards</text>
  <text x="460" y="771" text-anchor="middle" class="tiny">select then confirm</text>

  <rect x="550" y="732" width="140" height="50" rx="12" fill="#fff1f2" stroke="#dc2626" stroke-width="1.5"/>
  <text x="620" y="754" text-anchor="middle" class="tag" fill="#b91c1c">Guardian alerts</text>
  <text x="620" y="771" text-anchor="middle" class="tiny">block / consent</text>

  <rect x="704" y="732" width="70" height="50" rx="12" fill="#f8fafc" stroke="#64748b" stroke-width="1.5"/>
  <text x="739" y="754" text-anchor="middle" class="tag">Summary</text>
  <text x="739" y="771" text-anchor="middle" class="tiny">review</text>

  <line x1="174" y1="518" x2="140" y2="732" stroke="#16a34a" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arrow-green)"/>
  <line x1="993" y1="516" x2="300" y2="732" stroke="#d97706" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arrow-amber)"/>
  <line x1="574" y1="632" x2="460" y2="732" stroke="#2563eb" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arrow-blue)"/>
  <line x1="682" y1="498" x2="620" y2="732" stroke="#dc2626" stroke-width="2" stroke-dasharray="6 4" marker-end="url(#arrow-red)"/>

  <!-- Confirmation and action lifecycle -->
  <rect x="354" y="644" width="440" height="24" rx="12" fill="#dbeafe" stroke="#2563eb" stroke-width="1"/>
  <text x="574" y="660" text-anchor="middle" class="tag" fill="#1d4ed8">cards.render → card.selected → card.confirmed → card.action.status → audio.speaking / memory.write / notification.status</text>

  <!-- Eval and observability -->
  <rect x="44" y="556" width="260" height="76" rx="16" fill="#f8fafc" stroke="#64748b" stroke-width="2" class="panel"/>
  <text x="174" y="584" text-anchor="middle" class="label">Evals + Observability</text>
  <text x="174" y="607" text-anchor="middle" class="small">24 cases in `evals/cases.json`</text>
  <text x="174" y="624" text-anchor="middle" class="tiny">routes · tools · cards · product options · audio · traces</text>

  <line x1="354" y1="594" x2="304" y2="594" stroke="#64748b" stroke-width="2" marker-end="url(#arrow)"/>

  <!-- Bottom invariant -->
  <rect x="36" y="830" width="1114" height="18" rx="9" fill="#0f172a"/>
  <text x="593" y="843" text-anchor="middle" fill="#e2e8f0" font-size="10" font-weight="700">Invariant: faithful translation stays separate from agent advice · no medical recommendation · no side effects before backend confirmation · frontend displays backend-confirmed events</text>
</svg>
```

# After applying
Run these lightweight checks:
```bash
python - <<'PY'
from pathlib import Path
import xml.etree.ElementTree as ET
ET.parse(Path('docs/architecture_diagram.svg'))
print('svg ok')
PY
```
Then run at least:
```bash
cd frontend
npm run typecheck
```
If time permits, also run:
```bash
cd backend
./.venv/bin/python -m pytest -q
```

# Expected output
- README no longer says 7 evals or Python 3.10.
- README no longer includes the broken `export GOOGLE_API_KEY=$(grep...)` command.
- writeup no longer claims Guardian always runs first; it says Router and Guardian run in parallel.
- writeup no longer claims 141 passing tests or 7 green evals.
- SVG title no longer says “Sequential Agent Chain”; it shows current parallel/gated architecture.
- Existing uncommitted code changes outside these three docs must remain untouched.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
