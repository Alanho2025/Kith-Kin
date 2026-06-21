# Phase 07: ADK Router, Guardian, and Companion Implementation Plan

> Deterministic code uses pytest; nondeterministic behaviour uses eval RED-GREEN.

## Goal

Run Router and Guardian concurrently on every final turn, invoke Companion only when required, and produce typed Guardian-approved cards.

## Non-Goals

No ADK Workflow graph for `run_live`, direct medical advice, write/external MCP exposure, or exact-prose pytest assertions.

## Source of Truth

Agent boundaries in `AGENTS.md`, all specs, eval cases, official ADK API.

## Previous Phase Artifacts

Final transcripts, authorised RAG, read-only MCP toolset, runtime events.

## Entry Conditions

Phase 06 green.

## Exit Checkpoint

Parallel coverage and P0/P1 agent trajectory gates for this phase pass.

## Files

Create agent definitions, prompts, structured outputs, orchestrator service, deterministic safety backstop, proposal FunctionTools, unit tests and eval fixtures.

## Public Contracts

Router and Guardian return Pydantic outputs. Companion uses read-only `McpToolset` plus `submit_response_cards`; it does not use `output_schema` while tools are enabled. Guardian reviews proposed cards/actions again.

## Data Flows

Final turn→`asyncio.gather(router, guardian)`→block/fallback or Companion→read-only tools→typed proposal→Guardian card review→render. Guardian unavailable fails closed for sensitive paths.

## TDD/Eval Tasks

1. Deterministic concurrency and cancellation test.
2. Structured output parser failures.
3. PII/injection backstop tests.
4. Tool filter tests.
5. RED eval routing and Guardian coverage.
6. RED eval fuzzy drug and medical boundary.
7. GREEN prompt/agent configuration; rerun eval regression.

## Stop Conditions

Guardian skipped, write tool exposed, unstructured proposal accepted, or pytest asserting prose blocks Phase 08.

## Commit Boundaries

- `feat(agents): add parallel Router and Guardian`
- `feat(agents): add tool-using Companion proposals`

## Next Artifacts

Typed routes, Guardian decisions, approved card proposals, agent traces and eval results.

## Exact File Manifest

- Create agents `backend/app/agents/router_agent.py`, `guardian_agent.py`, `companion_agent.py`.
- Create prompt files `agents/prompts/router.md`, `guardian.md`, `companion.md`, each with version header `0.1.0`.
- Create schemas `backend/app/schemas/agent_outputs.py` and service `backend/app/services/turn_orchestrator.py`.
- Create deterministic backstop `backend/app/domain/safety_policy.py` additions and proposal tool `backend/app/agents/tools/submit_response_cards.py`.
- Create tests `backend/tests/unit/agents/test_outputs.py`, `test_tool_filter.py`, `test_safety_backstop.py`, `backend/tests/integration/agents/test_turn_orchestrator.py`.
- Modify machine eval cases for EVAL-002–006, 009–013. No migration or frontend changes.

## Exact Public Types and Signatures

```python
class RouteDecision(BaseModel):
    route_type: RouteType
    confidence: float
    reason_code: RouteReasonCode

class GuardianDecision(BaseModel):
    guardian_decision_id: str
    decision: GuardianDecisionType
    risk_level: GuardianRisk
    reason_code: GuardianReasonCode

class TurnOrchestrator:
    async def process_final_turn(
        self, event: TranscriptFinalEvent, context: TrustedRequestContext
    ) -> TurnOutcome: ...
```

Router reason enums are fixed in `runtime-event-contract.md`; free-form chain-of-thought is never accepted. Companion receives bounded `RetrievalContext` and only `memory_search`, `check_drug_interaction`, and `submit_response_cards`. `submit_response_cards` arguments are parsed into `CardSetProposal`; it performs no render or action. Guardian then reviews the exact proposal hash.

Stable errors are `ROUTER_UNAVAILABLE`, `ROUTER_OUTPUT_INVALID`, `GUARDIAN_UNAVAILABLE`, `GUARDIAN_OUTPUT_INVALID`, `GUARDIAN_BLOCKED`, `COMPANION_UNAVAILABLE`, `COMPANION_OUTPUT_INVALID`, and `DRUG_NAME_REQUIRED`. Sensitive flows fail closed when Guardian is unavailable.

## Flow Matrix

- Every final turn starts Router and Guardian with `asyncio.TaskGroup`; completion order does not change outcome.
- Guardian block cancels/ignores Companion proposals and emits the safe warning/card path.
- Passive translation runs Guardian but does not invoke Companion.
- Fuzzy name remains uncertain; no interaction tool until a concrete candidate is parent/pharmacist-confirmed.
- Memory/tool unavailable yields an explicit pharmacist-confirmation card; agents do not invent facts.
- Proposed cards and proposed write/notification actions receive a second Guardian review.

## Executable TDD and Eval Ledger

| Cycle | RED | Expected failure | GREEN |
|---|---|---|---|
| 07.1 | `test_turn_orchestrator.py::test_router_and_guardian_start_for_same_final` using barriers | one task never starts | TaskGroup fan-out |
| 07.2 | `test_outputs.py::test_invalid_structured_output_fails_closed` | raw text accepted | Pydantic output parser |
| 07.3 | `test_safety_backstop.py::test_payment_identity_address_are_blocked` | allow decision | deterministic backstop after model |
| 07.4 | `test_tool_filter.py::test_companion_has_read_only_tools_only` | write/notify visible | explicit tool filter |
| 07.5 | EVAL-002/013 RED expects Guardian trace for each final | missing trace | orchestration trace |
| 07.6 | EVAL-009 RED expects no interaction call for fuzzy name | tool called | uncertainty instruction/schema |
| 07.7 | EVAL-004/005/010 RED expects block/redaction | disclosure | Guardian prompt and policy gate |

Complete concurrency RED:

```python
@pytest.mark.asyncio
async def test_router_and_guardian_start_for_same_final(orchestrator, router, guardian, final_event):
    router.started = asyncio.Event()
    guardian.started = asyncio.Event()
    task = asyncio.create_task(orchestrator.process_final_turn(final_event, trusted_context()))
    await asyncio.wait_for(asyncio.gather(router.started.wait(), guardian.started.wait()), timeout=0.1)
    router.release.set()
    guardian.release.set()
    await task
```

Verify pytest RED by named assertion and eval RED by the named trajectory mismatch. GREEN changes one prompt/schema/orchestrator behaviour only, then runs the focused eval and all earlier agent evals. Refactor may consolidate prompt loading and trace mapping, never safety decisions or concurrency.

## Checkpoint, Cleanup, and Commit Boundary

Run backend unit/integration checks and `python -m evals.run evals/cases.json --case EVAL-002,EVAL-004,EVAL-005,EVAL-009,EVAL-010,EVAL-013`. Sanitised traces are written under ignored `evals/traces/`; cleanup deletes that directory only. No migration exists. Do not proceed if any final lacks Guardian evidence or any write/external tool is visible to Companion.
