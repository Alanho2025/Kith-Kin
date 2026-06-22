# Kith&Kin

Kith&Kin is a real-time Gemini companion for elderly Chinese-speaking parents navigating Australian pharmacy and GP visits. The MVP uses a React client, FastAPI backend proxy, one Gemini Live session, ADK agents, SQLite memory, and a stdio MCP tool server.

## Implemented scope

Phases 00–06 now provide the normative contracts, credential-backed Live validation record, secure tooling foundation, typed runtime/MCP/card schemas, an accessible React mock conversation UI, single-use app WebSocket tickets, a fake FastAPI WebSocket runtime, SQLite-backed RAG/MCP tools, and fixture-backed Gemini Live plus faithful translation-sidecar adapters. The real Gemini smoke for Phase 06 is currently `blocked_missing_credentials` until `GOOGLE_API_KEY` is supplied. Phase 03 browser sign-off is partially complete and tracked in `docs/PHASE_03_BROWSER_QA.md`.

## Setup

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# (No docker compose needed for database since SQLite is local-first)
uv sync --project backend --all-groups
npm --prefix frontend ci
```

`GOOGLE_API_KEY` is optional for tests and is required only for opt-in provider validation and later Live integration.

## Verify Phases 00–02

```bash
backend/.venv/bin/pytest backend/tests/unit -v
backend/.venv/bin/ruff check backend
backend/.venv/bin/mypy backend/app
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run test
npm --prefix frontend run build
```

Architecture and implementation order are defined in [`docs/CODE_PLAN.md`](docs/CODE_PLAN.md).
