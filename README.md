# Kith&Kin — 替你在场的人

**A real-time AI companion for elderly Chinese-speaking parents navigating Australian pharmacy and GP visits.**

[![Kaggle Capstone](https://img.shields.io/badge/Kaggle-Concierge%20Agents-20BEFF)](https://kaggle.com/competitions/vibecoding-agents-capstone-project)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

---

## The Problem

Every immigrant knows this moment: you're at work, and your parents are alone at the pharmacy counter. They can't understand what the pharmacist says, and they can't explain their medical history. Translation apps help with words — but they don't know about your dad's sulfa allergy, his blood pressure medication, or what the pharmacist recommended last time.

**Kith&Kin is the one who shows up when you can't.**

---

## What It Does

KK connects to the **Gemini Live API** through a single WebSocket session. It provides two parallel experiences from one audio stream:

| Track | What it does | Who controls it |
|-------|-------------|-----------------|
| **Visual** | Faithful real-time Chinese translation of the pharmacist's English — oversized text, append-only, never hallucinated | A lightweight Flash text model, **not** KK |
| **Voice + Cards** | KK listens for medication risks, searches past visit memory, and offers simple confirmable response cards | ADK multi-agent orchestration |

### The Hero Moment

**Visit 1:** The pharmacist mentions a new supplement. KK writes this to persistent memory and notifies the adult child.

**Visit 2 (days later):** KK opens the new session, recalls the prior advice, and proactively offers a card: *"Last time the pharmacist mentioned Coenzyme Q10 — want to ask about it today?"*

A translation app cannot do this. Only an agent with cross-session memory can.

---

## Architecture

```
┌─ User audio ──────────────────────────────────────────────┐
│                                                           │
│   ┌───────────────────────────────────────────────────┐   │
│   │  Gemini Live API (single WebSocket session)        │   │
│   └──────────┬──────────────┬────────────────┬────────┘   │
│              ↓              ↓                ↓            │
│   input_transcription   model audio      function-call    │
│   (English text)        (KK TTS)         (JSON cards)     │
│              ↓                            ↓               │
│   Flash text ──→ Chinese text      ADK Multi-Agent        │
│   translation    on screen         Router → Companion      │
│                                   Guardian (parallel)     │
│                                            ↓              │
│                                     MCP Memory Server     │
│                                     (SQLite — persistent) │
└───────────────────────────────────────────────────────────┘
```

### Three Course Concepts Demonstrated

1. **ADK Multi-Agent System** — `RouterAgent` classifies each turn, `CompanionAgent` generates response cards, `GuardianAgent` runs in parallel on every turn for safety. LLM-driven routing (not if-else keywords).

2. **MCP Server** — A standalone stdio process exposing `memory_search`, `memory_write`, `check_drug_interaction`, and `notify_family` tools. Connected via ADK's `McpToolset`.

3. **Security Features** — Ephemeral tokens (API key never reaches the frontend), injection detection on every turn, PII interception (credit card / Medicare / passport), and consent gating on every response card.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- A Google API key with Gemini Live API access (set in `backend/.env`)

### Setup

```bash
# 1. Clone and install
git clone https://github.com/Alanho2025/Kith-Kin.git
cd Kith-Kin

cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env

# 2. Backend
uv sync --project backend --all-groups

# 3. Frontend
npm --prefix frontend ci

# 4. Run MCP Memory Server (separate terminal)
python backend/app/adapters/mcp_tool_adapter.py

# 5. Run backend
cd backend && uv run uvicorn app.main:app --reload

# 6. Run frontend
cd frontend && npm run dev
```

> **Note:** `GOOGLE_API_KEY` is optional for tests. It is required only for opt-in provider validation and Live API integration.

---

## Project Structure

```
kith-and-kin/
├── backend/
│   ├── app/
│   │   ├── agents/          # Router, Companion, Guardian
│   │   │   └── prompts/     # System prompts for each agent
│   │   ├── adapters/        # Gemini Live, Translate, Text, MCP adapters
│   │   ├── api/routes/      # FastAPI endpoints (live, sessions, cards, health)
│   │   ├── core/            # Config, constants, error types
│   │   ├── db/models/       # SQLAlchemy models (alembic-managed)
│   │   ├── domain/          # Business rules (safety, cards, RAG, credentials)
│   │   ├── repositories/    # Data access layer
│   │   ├── services/        # Orchestration, translation, cards, tickets
│   │   └── schemas/         # Pydantic request/response models
│   └── tests/               # Unit + integration tests
├── frontend/
│   └── src/
│       ├── pages/           # StartPage, ConversationPage, VisitSummaryPage
│       ├── features/        # Conversation components and hooks
│       └── test/fixtures/   # Mock pharmacy and privacy flows
├── evals/
│   ├── cases.json           # 7 canonical eval cases
│   └── standalone_check.py  # Schema validator (no backend import needed)
├── docs/
│   ├── ARCHITECTURE.md      # Full system architecture
│   └── video_script.md      # ≤3 min demo video script
├── specs/                   # Runtime event, MCP tool, and response card contracts
└── .agents/
    └── AGENTS.md            # Cross-tool project context
```

---

## Evaluation

We maintain **7 eval cases** covering:

| Priority | Cases | What they verify |
|----------|-------|-----------------|
| P0 | 5 | Drug interaction, privacy interception (×2), prompt injection, cross-session recall |
| P1 | 1 | Fuzzy drug name handling |

Each case defines the expected route type, agent chain, tool calls, guardian decision, and forbidden outputs. Run with:

```bash
# Schema validation (no backend needed)
python evals/standalone_check.py

# Markdown report
python evals/standalone_check.py --report

# Full integration eval (requires running backend)
cd backend && uv run python -m pytest tests/
```

---

## Competition

- **Track:** Concierge Agents
- **Deadline:** July 6, 2026
- **Submission:** [Kaggle Capstone Project](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project)
- **Video:** [YouTube — Kith&Kin Demo](https://www.youtube.com/) *(link will be added before deadline)*

---

## License

This project is licensed under CC BY 4.0 — see the [Kaggle competition rules](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project/rules) for details.
