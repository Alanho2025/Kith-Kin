# Phase 08: Card Confirmation and Half-Duplex Audio Implementation Plan

## Goal

Implement one-time confirmation, idempotent actions, self-speak cancellation, and microphone mute ordering around TTS.

## Non-Goals

No visit-memory hero workflow or real notification.

## Source of Truth

Response-card and runtime specs; Phase 07 approved proposals.

## Previous Phase Artifacts

Card proposals, Guardian decisions, persistent confirmation repository.

## Entry Conditions

Phase 07 checkpoint green.

## Exit Checkpoint

Selection has no side effect; all action/replay/audio ordering tests and related evals pass.

## Files

Create CardService/action executor/audio coordinator, WS command handlers, HTTP recovery handler, tests and clock/audio fixtures. Add migrations only if Phase 05 schema requires a revision.

## Public Contracts

Card lifecycle and runtime events remain exactly as specs. Confirmation binds session, revision, action hash, Guardian decision, expiry, and idempotency key.

## Data Flows

Render→select→confirmation ID→confirm→execute. Duplicate returns stored result. TTS must emit mute before speaking and listening after completion. Self-speak cancels pending action.

## TDD Tasks

1. Selection produces no action.
2. Valid/expired/stale/cross-session confirmation.
3. Duplicate idempotency.
4. HTTP/WS equivalence.
5. Exact half-duplex event order.
6. TTS failure display fallback.
7. Self-speak cancellation/cleanup.

## Verification

Focused unit/integration tests, EVAL-003–008 and EVAL-014, full regression.

## Stop Conditions

Any pre-confirm side effect, repeated action, active mic during playback, or cross-session acceptance blocks Phase 09.

## Commit Boundaries

- `feat(cards): add one-time confirmation workflow`
- `feat(audio): enforce half-duplex playback`

## Next Artifacts

Confirmed action executor, consent audit, audio coordinator, and recovery path.

## Exact File Manifest

- Create `backend/app/services/card_service.py`, `confirmed_action_executor.py`, `audio_playback_coordinator.py`.
- Create `backend/app/domain/confirmation.py`, `backend/app/repositories/confirmation_repository.py` if not already provided by Phase 05.
- Create WebSocket command handler `backend/app/services/runtime_command_service.py` and keep `api/routes/cards.py` as a one-service-call recovery route.
- Create tests `backend/tests/unit/services/test_card_service.py`, `test_audio_playback_coordinator.py`, `backend/tests/integration/runtime/test_card_commands.py`, `test_half_duplex.py`.
- Create fixtures `backend/tests/fixtures/cards/approved_card_sets.py`, `confirmations.py`, `audio_gateway.py`.
- Modify frontend `useCardConfirmation.ts` only to consume server `confirmation_id`; no action text or arguments are added.
- Migration: add confirmation action hash/outcome columns only through `0002_confirmation_outcome.py` when absent from `0001`; otherwise no migration.

## Exact Service Contracts and Codes

```python
class CardService:
    async def select(
        self, command: CardSelectCommand, context: TrustedRequestContext
    ) -> CardSelectedResult: ...
    async def confirm(
        self, confirmation_id: UUID, context: TrustedRequestContext
    ) -> ConfirmationOutcome: ...
    async def cancel(
        self, confirmation_id: UUID, context: TrustedRequestContext
    ) -> None: ...

class AudioPlaybackCoordinator:
    async def play_confirmed(
        self, response: ApprovedSpeech, events: RuntimeEventSink
    ) -> PlaybackOutcome: ...
```

Confirmation stores `session_id`, `user_id`, card-set revision, card ID, action hash, Guardian decision ID, expiry, state, idempotency key, and terminal result. Codes are `CARD_NOT_FOUND`, `CARD_REVISION_STALE`, `CARD_EXPIRED`, `CONFIRMATION_EXPIRED`, `CONFIRMATION_SCOPE_INVALID`, `CONFIRMATION_REPLAYED`, `ACTION_INTEGRITY_FAILED`, `ACTION_BLOCKED`, and `TTS_UNAVAILABLE`.

## Normal, Replay, Failure, and Cleanup Flows

- Select validates active stored revision and returns confirmation metadata; no TTS, display, MCP, write, or notification method is reachable.
- Confirm locks the row, verifies scope/hash/Guardian/expiry, moves to executing, then stores one terminal outcome.
- Replay returns stored outcome with `replayed=true` and emits no duplicate side effect.
- Speech emits `audio.muted(true)` before `audio.speaking(started)`, then binary frames, completed/interrupted, mute false, listening true.
- TTS failure emits safe pharmacist-display fallback and restores listening in `finally`.
- Self-speak cancels unexecuted confirmation and pending playback generation; it invokes no tool.

## Executable TDD Ledger

| Cycle | RED node | Required assertion | GREEN |
|---|---|---|---|
| 08.1 | `test_card_service.py::test_select_has_zero_side_effects` | all fake action counts remain zero | selection branch only |
| 08.2 | parametrized expiry/stale/cross-session tests | stable error code | scope/integrity validator |
| 08.3 | `test_card_service.py::test_duplicate_confirm_returns_stored_outcome` | action count equals one | row lock/idempotency |
| 08.4 | `test_card_commands.py::test_http_and_ws_confirm_are_equivalent` | differing outcome | shared service |
| 08.5 | `test_half_duplex.py::test_mute_wraps_every_audio_frame` | ordered list mismatch | playback coordinator |
| 08.6 | `test_half_duplex.py::test_tts_failure_restores_listening` | final state muted | `finally` recovery |
| 08.7 | `test_card_commands.py::test_self_speak_cancels_without_action` | action observed | cancellation path |

Complete selection RED:

```python
@pytest.mark.asyncio
async def test_select_has_zero_side_effects(card_service, action_spy, approved_set, context):
    result = await card_service.select(
        CardSelectCommand(approved_set.card_set_id, approved_set.cards[0].card_id, 1), context
    )
    assert result.confirmation_id is not None
    assert action_spy.tts_calls == []
    assert action_spy.display_calls == []
    assert action_spy.mcp_calls == []
```

Verify each RED with the exact node. GREEN runs card/half-duplex groups plus EVAL-003–008 and EVAL-014. REFACTOR may extract transaction helpers and event builders only. Migration checkpoint is upgrade→downgrade→upgrade; rollback disables the command handler before reverting `0002`. Any pre-confirm action or missing listening restoration stops Phase 09.
