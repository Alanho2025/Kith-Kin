# Phase 11: End-to-End Demo Hardening Implementation Plan

## Goal

Make the local demo reproducible from a clean checkout and produce sanitised submission evidence.

## Non-Goals

No Cloud Run, Agent Runtime, production domain, real notification, or real health data.

## Source of Truth

All prior artifacts and Definition of Done.

## Previous Phase Artifacts

Passing product, evals, security gates, Docker services.

## Entry Conditions

Phase 10 pass bar met.

## Exit Checkpoint

Clean-checkout setup completes the full audio→translation→Guardian/cards→confirmation→memory/notification→recall loop.

## Files

Modify README, AGENTS, architecture/UI/code plans and commands. Create sanitised demo scripts/assets and release checklist. No new product boundary without a prior RED test.

## Public Contracts

No changes. Any required change returns to the owning phase/spec first.

## Data Flows

Test pharmacy, privacy, self-speak, translation failure, notification failure, reconnect and second-visit flows through the real browser and local backend.

## TDD/QA Tasks

1. Clean environment setup rehearsal.
2. Full automated suites.
3. Playwright CLI snapshot/interactions for each core flow.
4. Accessibility, responsive, audio mute and recovery audit.
5. Sanitised trace/screenshots and no-secrets scan.
6. AI-generated code boundary/import/API review.

## Rollback

Documentation/demo asset changes can be reverted independently; never delete user data or branches without approval.

## Stop Conditions

Any Definition of Done gap, command drift, P0 regression, sensitive artifact, or unexplained warning blocks recording.

## Commit Boundary

Suggested: `docs(demo): finalize reproducible pharmacy walkthrough`

## Final Artifacts

Local demo, passing reports, public setup guide, sanitised trace and screenshots.

## Exact File Manifest

- Modify only command/document drift in `README.md`, `AGENTS.md`, `docs/ARCHITECTURE.md`, `docs/UI_UX_PLAN.md`, `docs/CODE_PLAN.md`.
- Create `scripts/demo_preflight.py`, `scripts/reset_demo_data.py`, `scripts/run_demo_checks.py`.
- Create `docs/DEMO_RUNBOOK.md`, `docs/RELEASE_CHECKLIST.md` and sanitised assets under `docs/assets/demo/`.
- Create E2E tests `frontend/e2e/pharmacy-hero.spec.ts`, `privacy.spec.ts`, `fallbacks.spec.ts`, `reconnect.spec.ts` using the repository-selected Playwright CLI setup.
- Modify no contract or production boundary. Any discovered contract change returns to its owning phase and begins with RED.
- Migration: none. Demo reset calls repository cleanup against demo IDs only and refuses non-development environments.

## Preflight Public Contract and Errors

```python
class PreflightResult(BaseModel):
    dependencies_ok: bool
    database_ok: bool
    migrations_ok: bool
    demo_seed_ok: bool
    credentials: Literal["available", "blocked_missing_credentials", "not_required"]
    failed_checks: tuple[str, ...]

def run_preflight(settings: Settings) -> PreflightResult: ...
```

Stable script failures are `PREFLIGHT_DEPENDENCY_FAILED`, `PREFLIGHT_DATABASE_FAILED`, `PREFLIGHT_MIGRATION_DRIFT`, `PREFLIGHT_SEED_FAILED`, `PREFLIGHT_SECRET_SCAN_FAILED`, and `PREFLIGHT_EVAL_FAILED`. Scripts print no secret values and refuse production database URLs.

## Executable TDD and QA Ledger

| Cycle | RED | Expected failure | GREEN/document action |
|---|---|---|---|
| 11.1 | `test_demo_preflight.py::test_clean_environment_reports_each_missing_dependency` | script missing/wrong code | deterministic preflight |
| 11.2 | `test_reset_demo_data.py::test_refuses_production_environment` | destructive call reached | environment guard |
| 11.3 | `pharmacy-hero.spec.ts` | two-visit flow assertion | fix owning regression, not test wait |
| 11.4 | `privacy.spec.ts` | unconfirmed disclosure | return to Guardian/card owner |
| 11.5 | `fallbacks.spec.ts` | silent failure/translation overwrite | return to runtime/translation owner |
| 11.6 | `reconnect.spec.ts` | duplicate segment/action | return to ticket/runtime owner |
| 11.7 | clean-checkout command audit | README command differs/fails | update exact documentation |

Complete destructive-guard RED:

```python
def test_reset_refuses_production_environment(production_settings, demo_repository):
    with pytest.raises(RuntimeError, match="DEMO_RESET_FORBIDDEN"):
        reset_demo_data(production_settings, demo_repository)
    assert demo_repository.delete_calls == []
```

Verify focused RED/GREEN, then full backend/frontend/eval suites. Browser checks assert state, text, event order, focus, and network calls; snapshots are supporting evidence, not the only assertion. Refactor may remove duplicate runbook commands only after clean-checkout rerun.

## Final Checkpoint, Cleanup, and Commit Boundary

From a clean checkout: copy examples, install from locks, start PostgreSQL, migrate, seed, run tests/lint/typecheck/build/evals/secret scan, then execute the browser hero flow. Missing API credentials may block only the explicitly opt-in real Live proof; fake/fixture and all safety flows must pass. Cleanup removes demo rows by fixed synthetic IDs and ignored QA output. Do not record or push if any warning is unexplained or any artifact contains sensitive data.
