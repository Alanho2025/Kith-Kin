# Phase 00: Contract Reconciliation and Live Validation Implementation Plan

Status: completed with the real provider checkpoint recorded as `fail` on translation latency

> **For agentic workers:** execute inline with `superpowers:executing-plans` and `superpowers:test-driven-development`. Do not use real health data.

## Goal

Remove known source-document conflicts and create a reproducible, sanitised validation harness for agent-mode `input_transcription` and faithful text translation.

## Non-Goals

- No application server, database, frontend, ADK agent, or production Live integration.
- No claim that real Live validation passed without a credential-backed run.
- No Gemini ephemeral issuer.

## Source of Truth

`AGENTS.md`, all three `specs/` contracts, official Gemini Live documentation.

## Previous Phase Artifacts

None.

## Entry Conditions

- Repository documentation is readable.
- No real patient or pharmacy data is used.

## Exit Checkpoint

- Conflicting draft text is reconciled or explicitly marked legacy.
- A deterministic probe evaluator and sanitised provider fixture pass tests.
- A validation report records `pass`, `fail`, or `blocked_missing_credentials` without ambiguity.

## Files

### Create

- `backend/scripts/validate_live_transcription.py`
- `backend/app/domain/live_validation.py`
- `backend/tests/unit/domain/test_live_validation.py`
- `backend/tests/fixtures/live/input_transcription_session.json`
- `docs/LIVE_TRANSCRIPTION_VALIDATION.md`

### Modify

- `AGENTS.md`
- `docs/ARCHITECTURE.md`
- `docs/KithKin_Capstone_PRD.md`
- `docs/UI_UX_PLAN.md`
- `evals/EVAL_CASES.md`

### Test

- `backend/tests/unit/domain/test_live_validation.py`

### Fixtures

- Sanitised ten-utterance provider event fixture containing timestamps, final source transcripts, and translations.

### Migrations

None.

## Public Contracts

```python
class ValidationStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED_MISSING_CREDENTIALS = "blocked_missing_credentials"

class LiveValidationResult(BaseModel):
    status: ValidationStatus
    utterance_count: int
    usable_final_count: int
    transcription_p95_ms: int | None
    translation_p95_ms: int | None
    advice_contamination_count: int
    reasons: tuple[str, ...]

def evaluate_live_probe(samples: Sequence[LiveProbeSample]) -> LiveValidationResult: ...
```

Pass requires at least 9 usable finals from 10 utterances, transcription P95 at most 1,500 ms, translation P95 at most 1,000 ms, and zero advice contamination.

## Data Flows

- Normal: fixture/provider messages → normalised samples → evaluator → report.
- Missing credential: script writes no fabricated metrics and returns blocked status.
- Invalid provider data: evaluator fails with stable reason codes.
- Fallback: failed validation selects the documented Live Translate adapter for Phase 06; public runtime events remain unchanged.

## Task 1: Validation evaluator

### RED

Write tests for exact threshold pass, insufficient usable finals, excessive latency, and advice contamination.

### Verify RED

```bash
uv run --project backend pytest backend/tests/unit/domain/test_live_validation.py -v
```

Expected: collection/import failure for missing `app.domain.live_validation` before implementation.

### GREEN

Implement typed samples, percentile calculation using nearest-rank semantics, and stable reason codes.

### Verify GREEN

Run the focused test; all evaluator cases pass.

### REFACTOR

Extract only pure percentile and contamination predicates; rerun the focused suite.

## Task 2: Probe command and report

### RED

Add tests proving a missing credential returns `blocked_missing_credentials` and never reports pass.

### Verify RED

Run the focused command test and expect missing command function failure.

### GREEN

Implement the script with `--fixture` and explicit opt-in `--real` modes. Fixture mode is default; real mode requires `GOOGLE_API_KEY`.

### Verify GREEN

```bash
uv run --project backend python backend/scripts/validate_live_transcription.py --fixture backend/tests/fixtures/live/input_transcription_session.json
```

Expected: JSON result with deterministic status and zero sensitive content.

### REFACTOR

Keep provider connection behind an injected collector and rerun unit tests.

## Task 3: Documentation reconciliation

Update legacy tool names, Guardian topology, translation failure, backend-only MCP/RAG, and app-ticket terminology. Do not rewrite unrelated content.

## Rollback

Revert only Phase 00 files; no persistent data exists.

## Checkpoint Checklist

- [x] Fixture evaluation passes.
- [x] Real status is honestly recorded from a credential-backed probe.
- [x] No legacy knowledge tool remains as an expected MVP call.
- [x] All MCP access remains behind backend services and adapters.
- [x] The MVP app ticket is distinct from the future Gemini ephemeral token.

## Stop Conditions

Do not mark real validation passed without an authenticated run and sanitised evidence.

## Commit Boundary

Suggested: `docs(validation): reconcile contracts and record live probe status`

## Artifacts Exposed to Next Phase

Canonical terminology, validation evaluator, fixture, report status, and selected translation topology.

## Implementation Record

- Deterministic evaluator tests: `backend/tests/unit/domain/test_live_validation.py`.
- Missing-credential CLI test: `backend/tests/unit/test_live_validation_cli.py`.
- Fixture result: 10 utterances, 10 usable finals, transcription P95 900 ms, translation P95 410 ms, zero contamination.
- Real provider result: backend Live connection passed; 10/10 input transcriptions passed at 305 ms P95; the text sidecar failed at 2,056 ms P95 with `translation_latency_exceeded`.
- Manual review found default-thinking output-shape failures; minimal thinking restored faithful single-sample output, while a faithful ten-sample Flash-Lite comparison still failed latency under provider retries and free-tier limits.
- Evidence: `docs/LIVE_TRANSCRIPTION_VALIDATION.md`.
- Migration, seed, cleanup: none; fixture contains synthetic phrases only.
