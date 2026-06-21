# Phase 06: Gemini Live and Translation Implementation Plan

> Provider contract tests use complete sanitised messages before real SDK code.

## Goal

Connect one backend Gemini Live session, normalise audio/transcription, and translate final English utterances into append-only faithful Chinese.

## Non-Goals

No client-direct Gemini, Gemini ephemeral issuer, medical reasoning, or provider payload exposure.

## Source of Truth

Runtime spec, Phase 00 validation result, official Gemini Live API.

## Previous Phase Artifacts

Live gateway port, runtime DTOs, validation fixture, repositories.

## Entry Conditions

Phase 05 green and Phase 00 topology explicitly selected.

## Exit Checkpoint

Provider fixtures pass; opt-in real probe either passes thresholds or activates documented fallback.

## Files

Create Gemini Live/text/fallback adapters, provider schemas/errors, cancellation coordinator, contract tests, and sanitised fixtures. Modify live runtime wiring and settings only.

## Public Contracts

`GeminiLiveAdapter.open_session`, `send_audio`, `events`, `close`; `GeminiTextAdapter.translate_final`; provider errors map to stable application codes.

## Data Flows

Audio→Live; input transcription→normalised partial/final; final→translation sidecar; parallel runtime agent fan-out later. Failure retains English and emits fallback. Cancellation owns every task.

## TDD Tasks

1. Parse complete partial/final/audio/tool/provider-error fixtures.
2. Enforce one session and deterministic cleanup.
3. Translate only final utterances.
4. Append-only segment IDs and dedup.
5. Provider timeout/reconnect/fallback.
6. Opt-in credential-backed smoke.

## Verification

Focused adapter tests, runtime integration group, Phase 00 probe, ruff, mypy. Default suite never requires credentials.

## Stop Conditions

Second agent-mode Live session, partial translation, provider leakage, advice contamination, or unowned task blocks Phase 07.

## Commit Boundaries

- `feat(live): add Gemini live adapter`
- `feat(translation): add faithful final-turn sidecar`

## Next Artifacts

Normalised live events, faithful segments, provider fixtures, cancellation and fallback behaviour.

## Exact File Manifest

- Create `backend/app/adapters/gemini_live_adapter.py`, `gemini_text_adapter.py`, `gemini_live_translate_adapter.py`.
- Create `backend/app/adapters/provider_schemas.py`, `backend/app/services/translation_service.py`, `task_supervisor.py`.
- Create tests `backend/tests/unit/adapters/test_gemini_live_adapter.py`, `test_gemini_text_adapter.py`, `backend/tests/integration/runtime/test_live_translation_flow.py`.
- Create sanitised fixtures `backend/tests/fixtures/gemini/live_partial.json`, `live_final.json`, `live_audio.json`, `live_tool_call.json`, `live_error.json`, `text_translation.json`.
- Modify `live_runtime_service.py`, `core/config.py`, and dependency wiring. No schema, migration, seed, or frontend file changes are permitted.

## Public Ports and Stable Errors

```python
class LiveSessionPort(Protocol):
    async def send_audio(self, frame: bytes) -> None: ...
    def events(self) -> AsyncIterator[ProviderLiveEvent]: ...
    async def close(self) -> None: ...

class GeminiLiveGateway(Protocol):
    async def open_session(self, context: LiveSessionContext) -> LiveSessionPort: ...

class TranslationGateway(Protocol):
    async def translate_final(self, request: TranslationRequest) -> TranslationSegment: ...
```

Stable codes are `LIVE_UNAVAILABLE`, `LIVE_PROTOCOL_ERROR`, `LIVE_SESSION_LIMIT`, `TRANSCRIPTION_UNAVAILABLE`, `TRANSLATION_TIMEOUT`, `TRANSLATION_UNAVAILABLE`, and `TRANSLATION_ADVICE_CONTAMINATION`. Raw SDK exceptions and provider messages are logged only as redacted outcome codes.

## Exact Data and Failure Flows

- Normal: binary client frame → one `LiveSessionPort` → normalised provider event → `transcript.partial|final`; only final enters `TranslationGateway`; one immutable `translation.final` is appended.
- Duplicate final: dedup by provider event/utterance ID; no second translation request.
- Translation timeout/unavailable: retain English final, emit `fallback.show`, keep Chinese segments unchanged.
- Live disconnect: cancel audio sender and provider reader, close once, then apply runtime reconnect rules.
- D1 failure: when the recorded real probe fails, select `GeminiLiveTranslateAdapter` through settings; the public backend WebSocket and event shapes do not change.

## Executable TDD Ledger

| Cycle | RED node | Named failure | Minimal GREEN |
|---|---|---|---|
| 06.1 | `test_gemini_live_adapter.py::test_maps_complete_provider_fixtures` | fixture type rejected/missing adapter | strict provider normaliser |
| 06.2 | `test_live_translation_flow.py::test_opens_exactly_one_live_session` | call count 0/2 | lifecycle owner |
| 06.3 | `test_live_translation_flow.py::test_partial_never_calls_translation` | translation call observed | final-event filter |
| 06.4 | `test_live_translation_flow.py::test_final_appends_one_faithful_segment` | missing/wrong event | translation service |
| 06.5 | `test_live_translation_flow.py::test_duplicate_final_is_idempotent` | two segments | utterance dedup store |
| 06.6 | `test_live_translation_flow.py::test_translation_timeout_keeps_english` | Chinese summary/rewrite | safe fallback mapping |
| 06.7 | `test_live_translation_flow.py::test_disconnect_cancels_all_owned_tasks` | pending task remains | task supervisor |

Complete RED example:

```python
@pytest.mark.asyncio
async def test_partial_never_calls_translation(runtime, translation_gateway, partial_event):
    await runtime.handle_provider_event(partial_event)
    assert translation_gateway.requests == []
    assert runtime.events[-1].event_type == "transcript.partial"
```

Use full contract fakes implementing the ports; do not mock internal methods. Verify each RED with `backend/.venv/bin/pytest <node> -v`, GREEN with adapter/runtime groups, and refactor only normalisation helpers after pytest, ruff, and mypy pass.

## Credential Checkpoint and Rollback

Default CI runs fixtures only. The opt-in command is the Phase 00 `--real --capture` command and requires `GOOGLE_API_KEY`; its absence is reported as `blocked_missing_credentials`, not failure or pass. Rollback selects the fake adapter and removes Phase 06 wiring. A second agent-mode session, partial translation, or unowned task blocks Phase 07.
