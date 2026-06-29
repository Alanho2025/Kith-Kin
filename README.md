# Kith&Kin — 替你在场的人

**A real-time AI companion for elderly Chinese-speaking parents navigating Australian pharmacy and GP visits.**

[![Kaggle Capstone](https://img.shields.io/badge/Kaggle-Concierge%20Agents-20BEFF)](https://kaggle.com/competitions/vibecoding-agents-capstone-project)
[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

---

## 📖 The Problem

Every immigrant knows this moment: you're at work, and your parents are alone at the pharmacy counter. They can't understand what the pharmacist says, and they can't explain their medical history. Translation apps help with words — but they don't know about your dad's sulfa allergy, his blood pressure medication, or what the pharmacist recommended last time.

**Kith&Kin is the one who shows up when you can't.**

---

## ✨ Features

Kith&Kin connects to the **Gemini Live API** through a single WebSocket session. It provides two parallel experiences from one audio stream:

| Track | What it does | Who controls it |
|-------|-------------|-----------------|
| **Visual Track** | Faithful real-time Chinese translation of the pharmacist's English — oversized text, append-only, never hallucinated. | A lightweight Flash text model (translation sidecar) |
| **Voice + Card Track** | KK listens for medication risks, searches past visit memory, and offers simple confirmable response cards. | ADK multi-agent orchestration (Router, Companion, Guardian) |

### The Hero Moment
* **Visit 1:** The pharmacist mentions a new supplement. KK writes this to persistent memory and notifies the adult child.
* **Visit 2 (days later):** KK opens the new session, recalls the prior advice, and proactively offers a card: *"Last time the pharmacist mentioned Coenzyme Q10 — want to ask about it today?"*

A translation app cannot do this. Only an agent with cross-session memory can.

---

## 🏗️ Architecture

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

### Three Course Concepts Demonstrated

1. **ADK Multi-Agent System** — LLM-driven routing:
   * **Router Agent** — Classifies each turn ("routine translation" vs "needs decision"), pulls up Companion.
   * **Companion Agent** — Searches memory, calls drug-interaction check, generates confirm-cards. Matches garbled drug names phonetically/semantically.
   * **Guardian Agent** — Runs on every turn as a parallel safety layer (injection detection, PII interception, consent gating).
2. **MCP Server** — A standalone stdio process exposing `memory_search`, `memory_write`, `check_drug_interaction`, and `notify_family` tools, connected via ADK's `McpToolset`.
3. **Security Features** — Ephemeral tokens (API key never reaches the client), injection detection on every turn, PII interception (credit card / Medicare / passport), and consent gating on every response card.

---

## 🚀 Running the Project

### Prerequisites
* Python 3.10+
* Node.js 18+
* A Google API key with Gemini Live API access (set in `backend/.env` or `GOOGLE_API_KEY` env var)

### 1. Environment Setup

Copy template environment files to their local locations:
```bash
# Copy top-level and directory environment templates
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```
Ensure you set your `GOOGLE_API_KEY` in `backend/.env`.

### 2. Backend Setup
Initialize the Python virtual environment and install backend dependencies:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run SQLite database migrations and seed demo data (allergies, medication history, and patient profile):
```bash
# From the repository root. Running Alembic inside backend/ migrates the same
# default SQLite file the local backend reads: backend/kithkin.db.
cd backend
source .venv/bin/activate
alembic upgrade head

# Seed demo data into the same backend database from the repository root.
cd ..
backend/.venv/bin/python -m scripts.seed_demo_data --database-url sqlite+aiosqlite:///backend/kithkin.db

# Optional sanity check: the demo user/profile rows should be present.
sqlite3 backend/kithkin.db "select 'users', count(*) from users union all select 'medications', count(*) from medications union all select 'allergies', count(*) from allergies union all select 'visit_summaries', count(*) from visit_summaries;"
```

### 3. Frontend Setup
Install frontend npm packages:
```bash
cd frontend
npm install
```

### 4. Running Locally

To run the full application locally:

#### Step 4.1: Run the Backend Server
From the `backend` directory, run the FastAPI application on port 8000:
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Step 4.2: Run the Frontend App
From the `frontend` directory, start the Vite development server on port 5173:
```bash
cd frontend
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 🧪 Testing and Evals

We maintain comprehensive test suites across the entire stack.

### 1. Backend Pytest Suite
Run backend unit and integration tests (uses SQLite in-memory db and mocks the Gemini Live adapter):
```bash
cd backend
source .venv/bin/activate
pytest
```
*To run tests with code coverage:* `pytest --cov=app`

### 2. Frontend Vitest Suite
Run frontend component and unit tests:
```bash
cd frontend
npm run test
```
*To run tests in watch mode:* `npm run test:watch`

### 3. Playwright E2E Suite
Run end-to-end browser tests simulating the 3-turn pharmacy visit (automatically starts frontend Vite and backend Uvicorn servers):
```bash
cd frontend
npx playwright test
```

### 4. Agent Evals
Run the 17 canonical agent and safety acceptance evals (validating routing, safety boundaries, prompt injection, and tool trajectory):
```bash
# From the repository root directory, after backend setup.
# Fast offline contract check: validates the executable suite shape.
backend/.venv/bin/python -m pytest evals/test_runner.py -q

# Deterministic eval run. This does not require a Google API key.
backend/.venv/bin/python -m evals.run evals/cases.json

# Optional live Companion eval run. Requires GOOGLE_API_KEY in backend/.env.
export GOOGLE_API_KEY=$(grep '^GOOGLE_API_KEY=' backend/.env | cut -d '=' -f 2-)
backend/.venv/bin/python -m evals.run evals/cases.json --require-live-companion
```

### 5. Quality & Lint Gates
Run backend and frontend code quality checks:
```bash
# Backend lint check and formatting
cd backend
ruff check .
ruff format --check .
mypy app

# Frontend lint check and TypeScript typecheck
cd frontend
npm run lint
npm run typecheck
```

---

## 📂 Project Structure

```text
kith-and-kin/
├── backend/
│   ├── app/
│   │   ├── agents/          # Router, Companion, and Guardian agents
│   │   ├── adapters/        # Gemini Live API, text models, and MCP adapters
│   │   ├── api/routes/      # FastAPI endpoints (live connection, cards, health)
│   │   ├── db/              # SQLAlchemy engine and ORM models
│   │   ├── repositories/    # Database access repositories (sqlite persistence)
│   │   ├── services/        # Orchestration, cards confirmation, and commands
│   │   └── mcp_servers/     # Persistent stdio MCP memory server
│   └── tests/               # Backend unit and integration tests
├── frontend/
│   ├── src/
│   │   ├── pages/           # StartPage, ConversationPage, VisitSummaryPage
│   │   ├── components/      # UI components (StatusBar, Subtitles, Cards)
│   │   └── features/        # Conversation state, hooks, and API endpoints
│   └── e2e/                 # Playwright E2E browser tests
├── evals/
│   ├── cases.json           # Canonical acceptance evaluation cases
│   └── run.py               # Evaluation runner
├── docs/                    # Architecture, UI/UX, and Clean Code specs
└── specs/                   # Runtime event and card contract specifications
```

---

## 🏆 Competition

* **Track:** Concierge Agents
* **Deadline:** July 6, 2026
* **Submission:** [Kaggle Capstone Project](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project)
* **Demo Video:** [YouTube — Kith&Kin Demo](https://www.youtube.com/) *(link will be added before deadline)*

---

## 📄 License

This project is licensed under CC BY 4.0 — see the [Kaggle competition rules](https://www.kaggle.com/competitions/vibecoding-agents-capstone-project/rules) for details.
