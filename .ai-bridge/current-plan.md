# TDD-02 Allergy / Medication Cards Blocked

Updated: 2026-06-29T22:30:49.068Z
Workspace: /Users/heminghan/Kith-Kin
Target agent: Codex (codex)

## Plan

# Current Implementation Plan — TDD-02 Allergy / Medication Cards Blocked

Status: planning only. Do not edit product code yet.

## Scope decision

No explicit feature request was included after workspace connection. I inspected the current repo state and selected the narrowest active red item from `docs/pharmacy_counter_current_tdd_plan.md`: **TDD-02 — seeded profile lookup succeeds, but allergy / medication response cards are blocked before the user can confirm**.

`AGENTS.md` was requested but is not present at the workspace root. Follow README, architecture docs, and existing code style instead.

## 1. Goal

Fix the current real-backend pharmacy smoke failure where, after the pharmacist asks:

> Before I suggest anything, do you have any allergies or do you take blood pressure medicine?

backend profile lookup succeeds, but the card proposal/review path emits `live.cards.review_failed` and `fallback.show`, so the elderly user never sees a confirmable allergy / medication disclosure card.

Expected product behavior:

- Memory/profile lookup can find seeded demo facts: Penicillin allergy and Lisinopril / blood pressure medication.
- The UI renders safe, direct, split confirmation cards.
- The user can confirm one card.
- Confirmed speech can produce audio via the existing dedicated Gemini TTS path.
- Conversation turns remain clean; card confirmation must not directly append fake `KK 代说` turns.

## 2. Files to inspect

Already inspected:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/pharmacy_counter_current_tdd_plan.md`
- `handover.md`
- `backend/app/services/live_runtime_service.py`
- `backend/app/adapters/gemini_live_adapter.py`
- `backend/tests/unit/adapters/test_gemini_live_adapter.py`
- `frontend/e2e/pharmacy-backend.spec.ts`

Inspect next before coding:

- `backend/app/agents/companion_agent.py`
- Companion prompt file, likely under `backend/app/agents/prompts/`
- Guardian/card review implementation files under `backend/app/agents/`, `backend/app/services/`, or `backend/app/domain/`
- Card schema/model files defining `ResponseCard`, `CardSet`, `GuardianDecisionType`, `CardReview`, and action types
- Current tests around turn outcome/card review/profile lookup, especially `backend/tests/integration/runtime/test_gemini_live_transport.py` and `backend/tests/integration/runtime/test_live_translation_flow.py`
- Seed data tests: `backend/tests/integration/mcp/test_seed_demo_data.py`, `backend/tests/integration/mcp/test_drug_interaction.py`

## 3. Files likely to change

Likely backend changes:

- `backend/app/services/live_runtime_service.py`
  - Adjust card review fallback handling so a blocked ADK proposal can be replaced by deterministic safe split health-disclosure cards when the latest pharmacist turn asks for allergies / medication.
  - Avoid broad bypasses; only handle the explicit profile-disclosure scenario.

- Companion/Guardian files, exact path to confirm after inspection:
  - Tighten card proposal wording if cards are blocked because they look like meta-instructions, bundled medical disclosure, or unsafe direct advice.
  - Ensure safe cards are direct utterances, first-person, and pharmacist-facing.

Likely tests:

- `backend/tests/integration/runtime/test_gemini_live_transport.py` or `backend/tests/integration/runtime/test_live_translation_flow.py`
  - Add fail-first test proving profile lookup + allergy/current-medication question renders safe cards and does not emit `fallback.show`.

- `frontend/e2e/pharmacy-backend.spec.ts`
  - Keep existing red assertion for `/青霉素|Penicillin|过敏/`; do not weaken it.

Possibly unchanged:

- `backend/app/adapters/gemini_live_adapter.py`
  - It already ignores `model_turn.parts[].text` for transcript mapping and has tests for this. Do not touch unless new evidence shows the adapter still maps provider text into transcript.

## 4. Non-goals

- Do not rewrite the whole runtime orchestration.
- Do not change the one Gemini Live API session architecture.
- Do not add new dependencies.
- Do not relax Guardian medical-safety rules globally.
- Do not allow direct medical advice such as “take this medicine” or “this is safe.”
- Do not make the frontend append `KK 代说` on `card.confirmed` directly.
- Do not change unrelated product option, summary, checkout, or ticket-origin logic in this task.
- Do not connect to real clinical records or production data.

## 5. Step-by-step implementation

### Step 1 — Reproduce / confirm the red path

Run the narrow browser smoke if available:

```bash
cd frontend
npm run test:e2e -- e2e/pharmacy-backend.spec.ts
```

If that is too slow or requires local servers, first inspect logs or run the most relevant backend runtime tests.

Expected current red symptom:

- `tool.memory_search.result record_count=3`
- `turn.profile_lookup.result allergy_count=1 medication_count=1`
- then `live.cards.review_failed`
- then `fallback.show`
- no allergy/Penicillin card visible in the browser smoke.

### Step 2 — Add or strengthen the fail-first backend test

Create a focused runtime test for the exact pharmacist turn:

```text
Before I suggest anything, do you have any allergies or do you take blood pressure medicine?
```

The test should assert:

- Profile lookup produces seeded allergy/medication context.
- Runtime emits `cards.render`.
- Runtime does not emit `fallback.show` with `CARD_REVIEW_FAILED`.
- At least one card references Penicillin/allergy.
- If medication is included, medication and allergy are split into separate cards or clearly separated confirmation options.
- Cards are direct utterances, not meta labels.

### Step 3 — Identify why review blocks the card set

Trace the card proposal and review decision:

- Is Companion generating bundled allergy + medication disclosure in one card?
- Is Guardian blocking because card text contains direct medical judgment?
- Is Guardian blocking because text looks like meta-instruction (`Ask pharmacist`, `让 KK`, `The patient...`) rather than direct speech?
- Is `live_runtime_service._safe_card_set_for_turn()` called only after `outcome.card_review.decision is ALLOW`, causing deterministic split-card repair to never run when review blocks?

Important suspicion from inspected code:

- `_safe_card_set_for_turn()` can split bundled medication+allergy cards, but it is only called inside the `ALLOW` branch.
- If Guardian review returns `BLOCK`, the runtime goes straight to `fallback.show` and never gets a chance to replace the unsafe proposal with deterministic safe split cards.

### Step 4 — Implement the smallest safe fix

Preferred fix:

- Add a narrow deterministic repair path before emitting `CARD_REVIEW_FAILED` fallback.
- Only trigger it when:
  - latest pharmacist turn asks about allergy and/or medication, and
  - card proposal exists, and
  - card review blocked the proposal, and
  - the card text or profile context indicates medication/allergy disclosure risk.
- Replace the blocked proposal with `_split_health_disclosure_card_set(...)` or a new explicit helper that creates safe split disclosure cards.
- Register/render the repaired card set through the same `CardConfirmationService` path.
- Keep Guardian safety semantics intact by marking cards as requiring parent confirmation and guardian approval with a deterministic guardian decision id.

Alternative fix if root cause is Companion wording:

- Update Companion fallback/prompt card generation to produce already-safe split direct utterance cards.
- Keep runtime repair as a safety net only if needed.

### Step 5 — Keep card wording safe

Safe examples:

```text
I have a recorded Penicillin allergy. Could you please check whether that matters for these options?
```

```text
I have a record that I take Lisinopril. Could you please check whether that matters for these options?
```

Avoid:

```text
The patient is allergic to Penicillin.
Ask the pharmacist to check this.
You should take / avoid this medicine.
This option is safer.
```

### Step 6 — Verify no regression in existing safety gates

Re-run targeted tests first, then broader tests.

Make sure existing protections still hold:

- Provider thought/status text is not mapped to transcript.
- `card.confirmed` does not directly create fake conversation turns.
- Product option table tests remain unchanged.
- Guardian still blocks payment/private unsafe requests.

## 6. Verification commands

Run targeted backend tests first:

```bash
cd backend
./.venv/bin/python -m pytest tests/integration/runtime/test_gemini_live_transport.py -q
```

Run adapter test to avoid regressing provider text filtering:

```bash
cd backend
./.venv/bin/python -m pytest tests/unit/adapters/test_gemini_live_adapter.py -q
```

Run seed/profile tests:

```bash
cd backend
./.venv/bin/python -m pytest tests/integration/mcp/test_seed_demo_data.py tests/integration/mcp/test_drug_interaction.py -q
```

Run full backend test suite:

```bash
cd backend
./.venv/bin/python -m pytest tests -q
```

Run evals from repo root:

```bash
backend/.venv/bin/python evals/run.py evals/cases.json --report output/evals/conversation-debug-report.json
```

Run frontend tests:

```bash
cd frontend
npm run test
npm run typecheck
npm run lint
```

Run browser backend smoke:

```bash
cd frontend
npm run test:e2e -- e2e/pharmacy-backend.spec.ts
```

Final hygiene:

```bash
git diff --check
```

## 7. Risks

- If the repair path is too broad, it could weaken Guardian and allow unsafe health disclosure.
- If deterministic cards reveal profile facts without a user confirmation requirement, privacy requirements are violated.
- If card text is too meta, it may pass backend tests but still feel unnatural to elderly users.
- If tests rely on exact Chinese wording, they may become brittle; prefer semantic regex around allergy/medication where possible.
- If the browser smoke requires real Gemini/API state, it may be flaky; keep mandatory CI on fake provider + deterministic trace, and use live-provider smoke as opt-in.
- No `AGENTS.md` exists, so Codex must follow the repo docs and this plan strictly instead of relying on root agent instructions.

## Codex execution rule

Implement only the above TDD-02 plan. Do not fix TDD-03 through TDD-08 in this pass. Stop and report if the root cause is not card review / safe-card replacement.

## Implementation contract

- Work from this plan in small, reviewable steps.
- Keep edits scoped to the requested task and existing project conventions.
- Run focused verification before handing work back.
- Update .ai-bridge/agent-status.md with files touched, checks run, results, blockers, and review notes.
- Save the final review diff to .ai-bridge/implementation-diff.patch when practical.
- Append notable execution events to .ai-bridge/execution-log.jsonl when the implementation agent supports logging.
