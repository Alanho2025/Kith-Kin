# Phase 10: Security, Observability, and Evaluation Implementation Plan

## Goal

Harden abuse paths, implement allowlist traces and retention, and make all canonical evals executable.

## Non-Goals

No production SIEM, cloud tracing, real patient data, or HTTP eval endpoint.

## Source of Truth

Security rules, eval Markdown, specs, retention requirements.

## Previous Phase Artifacts

Full local product flow and trace repository.

## Entry Conditions

Phase 09 green.

## Exit Checkpoint

All P0, at least 80% P1, secret scan, abuse regression, retention and trace-shape tests pass.

## Files

Create redaction/trace/retention services, secret scanner, machine eval cases, eval runner/judges, robustness tests and sanitised trace fixtures.

## Public Contracts

Trace allowlists by event type; no raw payload logging. Eval output contains case ID, pass/fail dimensions, redacted trace path and failure codes.

## Data Flows

Runtime event→allowlist mapper→trace repository. Eval input→isolated seeded session→trajectory→deterministic checks/Gemini judge→result. Cleanup deletes expired sensitive rows while preserving minimal consent evidence.

## TDD/Eval Tasks

1. Secret and frontend-bundle scan.
2. Trace allowlist and PII fixtures.
3. Injection/cross-session/replay abuse regression.
4. Retention cleanup and rollback.
5. Convert all 15 cases.
6. Eval RED baseline, targeted fixes, regression comparison.

## Stop Conditions

Any P0 fail, raw PII/token trace, default real credential dependency, or eval/Markdown drift blocks Phase 11.

## Commit Boundaries

- `feat(security): add allowlisted traces and abuse guards`
- `feat(evals): add canonical pharmacy evaluation runner`

## Next Artifacts

Release-quality eval report, trace evidence, retention service and security scan.

## Exact File Manifest

- Create `backend/app/core/logging.py`, `backend/app/services/trace_service.py`, `redaction_service.py`, `retention_service.py`.
- Modify `scripts/check_no_secrets.py` to add fixture payload and generated trace scanning while preserving its Phase 01 source/bundle checks.
- Create `evals/cases.json`, `evals/run.py`, `evals/judges.py`, `evals/trajectory.py`.
- Create tests `backend/tests/unit/security/test_redaction.py`, `test_trace_allowlist.py`, `test_secret_scan.py`, `backend/tests/integration/security/test_abuse_paths.py`, `test_retention.py`, `backend/tests/contract/test_eval_markdown_sync.py`.
- Create sanitised trace fixtures for all 15 eval cases; generated run results remain under ignored `evals/results/` and `evals/traces/`.
- Migration `0004_retention_metadata.py` adds retention category/deletion timestamps only when absent; no raw payload column.

## Public Types and Output Contract

```python
class TraceService:
    async def record(self, event: TraceInput, context: TrustedRequestContext) -> None: ...

class RetentionService:
    async def delete_expired(self, *, now: datetime, batch_size: int = 500) -> RetentionResult: ...

class EvalResult(BaseModel):
    case_id: str
    passed: bool
    deterministic_checks: dict[str, bool]
    judge_score: float | None
    failure_codes: tuple[str, ...]
    redacted_trace_path: str
```

Trace schemas use per-event allowlists. Route/Guardian/tool traces contain IDs, enum codes, count, latency, outcome, and replay flags only. Raw transcript, prompt, provider response, profile, medication values, identity/payment/address/family data, tokens, and destinations are forbidden.

## Security and Eval Flows

- Runtime metadata → trace allowlist mapper → redaction backstop → repository.
- Known sensitive fixture must produce `[REDACTED]` only in logs/traces/untrusted inbound fields; authorised health context remains available inside services and is never copied into the trace.
- Eval runner creates isolated synthetic session data, runs one case, performs deterministic route/tool/Guardian/confirmation checks, optionally invokes a Gemini judge, writes sanitised output, then cleans its rows.
- Judge unavailable leaves `judge_score=null` and fails only cases whose declared criterion requires it; deterministic P0 gates never depend on a judge.
- Retention deletes expired visit/trace detail in batches while retaining minimal consent/action evidence required by the plan.

## Executable TDD/Eval Ledger

| Cycle | RED node | Required failure | GREEN |
|---|---|---|---|
| 10.1 | `test_secret_scan.py::test_scans_ignored_frontend_dist` | injected marker not found | scanner dist traversal |
| 10.2 | `test_trace_allowlist.py::test_full_profile_cannot_enter_trace` | field present | event allowlist models |
| 10.3 | `test_redaction.py` parametrized card/passport/Medicare/address | unredacted token | redaction backstop |
| 10.4 | `test_abuse_paths.py` injection/cross-session/replay | disclosure/action | safety regression fixes |
| 10.5 | `test_retention.py::test_batch_cleanup_preserves_consent_evidence` | wrong deletion set | retention service |
| 10.6 | `test_eval_markdown_sync.py::test_all_15_ids_match_json` | ID drift | machine cases |
| 10.7 | full eval baseline | P0/P1 trajectory mismatch | one targeted change per case |

Representative trace RED:

```python
def test_full_profile_cannot_enter_trace(trace_service, profile, trace_repository):
    trace_service.record_sync(ToolTraceInput(tool_name="memory_search", raw_result=profile))
    stored = trace_repository.last()
    assert set(stored.payload) == {"query_category", "record_count", "latency_ms", "outcome", "truncated"}
    assert "Lisinopril" not in json.dumps(stored.payload)
```

Verify each unit/integration RED by node. Eval RED records the exact failed dimension; GREEN changes only its owning prompt/policy/service and reruns that case plus all earlier P0. Refactor is restricted to shared allowlist/judge plumbing. No real health data or default credential dependency.

## Migration, Cleanup, Checkpoint, and Rollback

Run migration upgrade→downgrade→upgrade, `python -m evals.run evals/cases.json`, secret scan, full backend/frontend checks, and retention against the test database. Expected: all P0, at least 80% P1, zero forbidden disclosure/advice, and no secret marker. Cleanup removes generated trace/result directories and isolated eval rows. Any P0 failure or unredacted trace blocks Phase 11.
