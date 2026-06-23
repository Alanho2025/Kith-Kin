# Kith&Kin: The One Who Shows Up When You Can't

**Track:** Concierge Agents
**Team:** Kith&Kin

---

## The Problem

Every immigrant knows this moment: you're at work, and your parents are alone at the pharmacy counter. They can't understand what the pharmacist says. They can't explain their medical history. They can't ask the questions that matter.

Translation apps help with words — but they don't know about your dad's sulfa allergy, his blood pressure medication, or what the pharmacist recommended last time. They can't tell the difference between "try this new medication" and "give me your credit card number." And when the visit ends, they forget everything.

Kith&Kin is an AI companion that fills this gap. It provides real-time faithful translation, risk-aware decision support, persistent cross-session memory, and family-in-the-loop notifications — all through a single voice interface designed for elderly users.

---

## Why an Agent?

A translation app fails here because it has no memory, no context, no risk awareness. An agent succeeds because it can:

1. **Persist across sessions** — remember last visit's advice and proactively raise it next time
2. **Access private context** — check the parent's medication profile against new prescriptions
3. **Distinguish risk types** — recognize that "credit card number" is not a translation task but a privacy event
4. **Gate on consent** — never speak for the parent without explicit confirmation

These are not translation problems. They are agent problems.

---

## Architecture

[architecture_diagram.svg]

The system runs on a single Gemini Live API WebSocket session. Three channels are parsed from this one stream:

- **Visual track (faithful translation):** `input_transcription` from the Live API is passed to a lightweight Flash text model for English-to-Chinese translation. This is displayed in oversized, append-only text on screen. KK never modifies or generates this translation — it remains faithful to the original.

- **Voice/card track (agent reasoning):** The same audio stream is handled by an ADK multi-agent graph. Router and Guardian evaluate each turn concurrently; the Companion LlmAgent is invoked only after Guardian clears the turn (fail-closed) — if Guardian blocks, the LLM is never called. The Companion searches memory, checks drug interactions, and composes confirmable response cards.

- **Tool layer (MCP server):** A stdio MCP server exposes deterministic tools for memory search/write, drug interaction checking, and family notification. All medical facts come from tools — the LLM never generates them.

**Safety ordering:** The Guardian runs before the Companion on every turn. If it detects a prompt injection, credit card request, passport request, or Medicare number request, it short-circuits the turn immediately — the sensitive request never reaches the LLM.

---

## Three Course Concepts

### 1. ADK Multi-Agent System

The system uses three ADK agents orchestrated by a root `OrchestratorAgent`:

- **Guardian** — ADK agent wrapping deterministic safety checks (injection detection, PII interception). Fail-closed: if triggered, the turn is blocked before reaching any LLM.
- **Router** — ADK agent wrapping deterministic keyword classification. Routes turns based on transcript content.
- **Companion** — ADK `LlmAgent` (`gemini-2.5-flash`) with MCP tool access. Searches memory, checks drug interactions, and composes response cards.

The `OrchestratorAgent` runs Router and Guardian concurrently on every turn. The Companion LLM is gated behind Guardian's decision: if Guardian blocks (credit card, passport, Medicare, prompt injection), the LLM is never invoked. Only when Guardian clears the turn does the Companion receive the context to call tools and compose cards.

All three agents are real ADK agents in the orchestration graph (`google.adk.agents`). Only the Companion uses an LLM — routing and safety remain deterministic for reliability, auditability, and demo safety. This design is verified by 141 passing tests and 7 green eval cases including EVAL-015 (cross-session recall).

### 2. MCP Server

A stdio-based MCP server exposes four tools to the Companion agent:

| Tool | Description | Deterministic? |
|------|-------------|----------------|
| `memory_search` | Search patient profile, visit history, medication records | ✅ |
| `memory_write` | Persist new facts after each visit | ✅ |
| `check_drug_interaction` | Look up drug-drug interactions from a version-controlled knowledge base | ✅ |
| `notify_family` | Record a notification stub for the adult child | ✅ |

All tools are deterministic database lookups or writes. The LLM decides when to call them but never generates medical facts itself.

**Cross-session recall:** On session start, the system silently pre-fetches the most recent visit summaries. If an unresolved question or recommendation exists (e.g. "try Coenzyme Q10 for statin-related muscle pain"), the Companion proactively offers a response card asking the parent if they want to raise it.

### 3. Security Features

Three layers of protection:

1. **Ephemeral tokens** — The frontend uses a backend-issued, single-use, short-lived WebSocket ticket. The Gemini API key never enters the client code.

2. **Guardian interception** — Every turn passes through a deterministic safety check before reaching the LLM. Credit card, passport, Medicare number, and home address requests are blocked and replaced with a privacy warning card. Prompt injection attempts are detected and blocked.

3. **Consent gating** — Every response card requires explicit parent confirmation (tap-to-confirm) before KK speaks it. The parent always stays in control.

---

## Demo: Two-Visit Hero Flow

**Visit 1:** The pharmacist mentions trying Coenzyme Q10 for statin-related muscle pain. KK writes this to persistent memory and offers to notify the adult child.

**Visit 2 (days later):** The parent returns for another prescription. KK opens the session, detects the prior visit record, and proactively offers a card: "Last time the pharmacist mentioned Coenzyme Q10 — want to ask about it today?"

This cross-session recall is the hero moment. A translation app cannot do this. Only an agent with persistent memory and proactive reasoning can.

---

## Evaluation

We maintain 7 canonical eval cases covering the core scenarios:

| ID | Scenario | What it tests |
|----|----------|---------------|
| EVAL-002 | Pharmacist suggests ibuprofen | Drug interaction check, memory search |
| EVAL-004 | Pharmacist asks for credit card | Privacy interception, block |
| EVAL-005 | Pharmacist asks for Medicare | Identity gate, block |
| EVAL-009 | Fuzzy drug name "listen to pro" | ASR error handling, confirm card |
| EVAL-010 | "Ignore previous instructions" | Prompt injection, block |
| EVAL-013 | "Do you have any allergies?" | Guardian parallel coverage |
| EVAL-015 | Cross-session recall (CoQ10) | Proactive memory recall on new visit |

Each case defines the expected route type, agent chain, tool calls, Guardian decision, and forbidden outputs. Run with `evals/run.py` for end-to-end verification or `evals/standalone_check.py` for schema validation.

---

## Project Journey

The project was built over two weeks by a team of three, applying concepts from Google's 5-Day AI Agents: Intensive Vibe Coding course. The development followed a phased approach:

- **Phase 00-04:** Contract specs, runtime events, MCP tool contracts, response card schemas, accessibility-focused UI design
- **Phase 05-08:** FastAPI backend, Gemini Live adapter, deterministic agent stubs, confirmation workflow, half-duplex audio ordering, database models and migrations
- **Phase 09:** Visit completion service, cross-session memory persistence, proactive recall, family notification stub, integration tests
- **Phase 10-11:** Architecture documentation, evaluation framework, video script, competition writeup

The ADK multi-agent integration (converting deterministic stubs to real ADK agents) was the final architectural step, completing the transition from prototype to competition-ready submission.

---

## Repository

github.com/Alanho2025/Kith-Kin

The repository includes the complete backend (FastAPI + ADK + MCP + SQLite), frontend (React + TypeScript + Tailwind), eval framework (7 cases with runner), spec contracts, and documentation.
