# Pharmacy Counter Current TDD Plan

Updated: 2026-06-30

## Current Verification Baseline

This plan is based on the run after adding conversation console diagnostics across the frontend runtime, hooks, page actions, card actions, session routing, audio recorder/player, backend runtime/tool diagnostics, dedicated Gemini TTS, and deterministic pharmacy demo seed data.

Commands run:

- `npm run typecheck` in `frontend`: pass
- `npm run lint` in `frontend`: pass
- `npm run test` in `frontend`: 14 files, 54 tests passed after the latest large-print subtitle correction, Playwright CI database-path regression test, and deterministic/live backend mode split
- `backend/.venv/bin/python -m pytest backend/tests`: 264 passed, 1 skipped, 6 warnings
- `backend/.venv/bin/python -m pytest backend/tests/integration/mcp/test_seed_demo_data.py backend/tests/integration/mcp/test_drug_interaction.py`: 8 passed after the seed expansion
- `backend/.venv/bin/python evals/run.py evals/cases.json --report output/evals/conversation-debug-report.json`: 24/24 passed, 23/23 P0 passed
- `npm run test:e2e -- e2e/pharmacy-backend.spec.ts`: 1 passed after the safe replacement allergy card, Gemini TTS binary audio path, product options, and summary were verified.
- `PLAYWRIGHT_BACKEND_MODE=deterministic npx playwright test e2e/pharmacy-backend-deterministic.spec.ts`: added as the merge-required CI browser smoke for real backend + seeded DB without real Gemini. Local execution was blocked by the Codex escalated-command usage limit during this CI split; GitHub Actions is expected to run it as part of `deterministic-e2e`.

Important reading of this baseline:

- The Round 1 deterministic gaps are green in tests/evals. The strengthened real-backend browser flow is now green after the Notion-review fixes and the latest large-print subtitle correction.
- The old no-audio failure is fixed for confirmed cards through the dedicated Gemini TTS path. The live run now logs `gemini_tts.synthesize.ok`, `live.card_tts.audio_sent`, browser `runtime.websocket.audio.in`, and `audio_player.play.scheduled`.
- The old "did it read the database?" question is now observable and separated from card logic. With seeded demo data, the allergy/safety question logs `tool.memory_search.result record_count=4`, `turn.profile_lookup.result allergy_count=1 medication_count=1`.
- The previous browser red failure was card generation/review: after the profile lookup succeeded, ADK proposed cards but deterministic review returned `card_review=block`, then runtime emitted `live.cards.review_failed` and `fallback.show`, so the UI had no allergy card to confirm. That failure is now covered by deterministic safe replacement cards and the backend smoke verified the allergy card can be confirmed.
- Product clarification from 2026-06-30: the left large-print translation area is not append-only. It must show only the latest faithful pharmacist translation. Conversation history belongs in the right log, debug trace, and turn history.

## Current Gaps And TDD Plan

| ID | Current gap / bug risk | New test or eval | What it proves | Edge cases |
|---|---|---|---|---|
| TDD-01 | Console diagnostics are manual-only; no test proves every conversation stage emits a useful debug breadcrumb. | Add Playwright console-capture test around backend smoke. Assert required `[KK conversation]` labels appear in order. | Session create, ticket, WebSocket open, typed fallback, runtime event receive, reducer state, card select/confirm, audio inbound, audio playback, summary are all observable. | Mock mode vs backend mode; ticket 403; card cancel; no-card passive translation; session end. |
| TDD-02 | Allergy/medication profile lookup succeeds, but LLM response cards can be blocked before the user can confirm. | Integration test for seeded profile + allergy/current-medication question expects direct, split, pharmacist-confirmation cards and no `fallback.show`; Playwright backend smoke confirms the allergy card and Gemini TTS path. | The fallback path is deterministic and safe even when ADK/card review blocks a bundled card proposal. | Allergy-only, medication-only, combined allergy+medication question, card review missing state, blocked ADK proposal. |
| TDD-03 | Full purchase/payment flow is still not browser-verified; current backend smoke ends after product options and summary. | Add `frontend/e2e/pharmacy-checkout-backend.spec.ts` using real backend typed pharmacist flow through parent purchase intent, pharmacist payment instruction, parent confirmation, session end. | Product goal covers checkout, not just product comparison. | Cash/card wording; final price; no medical recommendation; cancel session end; duplicate end click. |
| TDD-04 | Main workspace translation semantics were ambiguous: prior tests/specs treated the left large-print Chinese area as append-only, but product behavior requires only the latest pharmacist translation there. | `TwoLayerSubtitle.test.tsx` and `ConversationPage.test.tsx` assert that consecutive translations leave only the latest sentence in the large-print region while turn/log history still preserves prior translations. | The parent-facing primary area stays current and readable instead of accumulating old context; the right log/debug trace remain available for history. | Long three-product sentence; cards after table; listening restored; passive translation only; repeated segment replay. |
| TDD-05 | Real Gemini Live behavior is only covered by one Playwright smoke, not by a reusable opt-in provider eval with trace output. | Add opt-in eval `live_gemini_pharmacy_smoke` that records sanitized provider/runtime/browser trace and validates the same contracts as E18-E24. | Future provider changes cannot silently reintroduce thought text, missing audio, or speaker mismatch. | Missing key should skip with explicit reason; provider timeout; no audio; thought/status text; rate limit. |
| TDD-06 | Browser backend smoke previously used an empty temporary DB, so product-goal profile checks could be mistaken for product bugs. | Keep Playwright `webServer` seeding `scripts/seed_demo_data.py`; keep `test_seed_demo_data.py` content assertions for Lisinopril, Penicillin, prior follow-up, overseas medicine active-ingredient note, and OTC brand knowledge. | The e2e harness always starts with deterministic authorised profile data. | Reused server mode, cleanup idempotency, missing OTC brand, extra product facts leaking from memory. |
| TDD-07 | Product decision remains unresolved: exact copy for verified profile fact disclosure must be direct speech but must not become AI medical judgment. | Add paired agent/eval tests for identity/allergy/medication factual disclosure cards. | The prompt and guardian enforce "share confirmed fact, ask pharmacist to check" instead of meta instructions or bundled broad disclosure. | Allergy-only; medication-only; combined pharmacist question; profile missing; explicit user consent. |
| TDD-08 | Test hygiene warnings can hide real regressions over time. | Add cleanup tasks/tests for the `AsyncMock` unawaited warning in `test_echo_filtering.py`, frontend Vitest localStorage warning, and Playwright teardown `ECONNRESET` noise. | CI output stays signal-heavy; unexpected warnings become visible. | Live smoke skipped without key; local vs CI environment differences. |

## Red-Green-Refactor Sequence

1. Red: add Playwright console-capture assertions for the required debug labels.
   Green: stabilize `conversationDebug` payload schema and label names if needed.
   Refactor: document the debug label contract in the test file.

2. Red: assert seeded allergy/current-medication question renders direct disclosure cards instead of `fallback.show`.
   Green: fix card review/safe-card fallback ordering so blocked or missing ADK review still produces safe split confirmation cards.
   Refactor: make health-disclosure card construction explicit and deterministic.

3. Red: extend browser backend flow through purchase/payment/summary.
   Green: fix any runtime or UI issue that prevents checkout completion.
   Refactor: split the long browser flow into reusable typed-pharmacist helpers.

4. Red: assert the large-print main translation shows only the latest faithful final while log/history keep prior turns.
   Green: render only the latest Chinese segment in `TwoLayerSubtitle`, without deleting reducer turn history.
   Refactor: keep display selectors scoped to `aria-label="忠实中文翻译"` so tests do not confuse main subtitles with the right log.

5. Red: add opt-in live-provider eval that writes a sanitized trace.
   Green: make the live eval satisfy E18-E24 contracts against current Gemini Live behavior.
   Refactor: keep mandatory CI on fake provider + trace replay; run live provider manually or nightly.

## Done Criteria For The Next E2E-Ready Claim

- Required console debug stages are covered by Playwright, not just visible manually.
- Confirmed card speech has both binary frame delivery and frontend playback scheduling evidence.
- Browser backend flow covers product comparison, purchase/payment, and visit summary.
- Main workspace shows only the latest useful pharmacist translation through no-card, cards, product table, and listening transitions; history remains in the right log/debug trace.
- A fresh sanitized live trace can be replayed by evals without exposing secrets, cookies, raw audio, or raw PII.
