# Kith&Kin

Kith&Kin is a real-time Gemini companion for elderly Chinese-speaking parents navigating Australian pharmacy and GP visits. The MVP uses a React client, FastAPI backend proxy, one Gemini Live session, ADK agents, SQLite memory, and a stdio MCP tool server.

## Implemented scope

Phases 00–02 provide the normative contracts, source reconciliation, Live transcription validation harness, secure environment/tooling foundation, typed runtime/MCP/card schemas, backend state machines, and frontend wire mapper. The authenticated Live provider checkpoint remains explicitly credential-blocked.

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
