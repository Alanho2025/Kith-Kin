# Phase 04: Session Ticket and Fake WebSocket Runtime Implementation Plan

Status: implemented and accepted

> Execute each ticket and socket behaviour with an observed failing integration test first.

## Goal

Provide thin session APIs, same-origin single-use app tickets, and a fake-adapter live WebSocket implementing the runtime contract.

## Non-Goals

No Gemini, ADK, MCP, PostgreSQL health data, or real TTS.

## Source of Truth

Master plan credential contract, runtime spec, Phase 02 schemas.

## Previous Phase Artifacts

Settings, typed runtime events, UI runtime interface.

## Entry Conditions

Phases 01–03 green.

## Exit Checkpoint

Ticket abuse, event ordering, replay, reconnect, and fake vertical-flow tests pass.

## Files

### Create

Session/live/card/health routes; dependencies; error handlers; session, ticket, card, and live-runtime services; fake Live gateway; integration tests; clock/key fixtures.

### Modify

FastAPI app factory and frontend runtime adapter.

### Test

HTTP, cookie, WebSocket, origin, replay, sequence, reconnect, and recovery endpoint tests.

### Fixtures

Fixed clock, signing key, fake sessions, complete runtime event stream.

### Migrations

None; use an injected in-memory ticket store only until Phase 05.

## Public Contracts

`POST /sessions`, `/sessions/{id}/ticket`, `/sessions/{id}/end`, `/cards/confirm`, and `WS /sessions/{id}/live`. Cookie name and close codes are fixed by the master plan.

## Data Flows

Ticket issue binds server-resolved user/session/origin. Upgrade validates and atomically consumes before accept. Reconnect requests a new ticket. Commands are ignored before validation. Sequence gaps trigger replay or visible failure.

## TDD Tasks

1. Valid single-use ticket.
2. Expiry/signature `4401`.
3. Origin/audience/purpose/session/user `4403`.
4. Replay `4409`; inactive session `4410`.
5. Fake binary/audio and JSON event flow.
6. Sequence/dedup/resume.
7. HTTP confirm recovery shares CardService idempotency.

RED command: `uv run --project backend pytest <focused-test> -v`; GREEN reruns focused and integration group; refactor may only extract ports and validators.

## Rollback

Stop server and remove Phase 04 files; no persistent records exist.

## Checkpoint

Backend integration suite and frontend fake-backend contract flow pass with no credential in JSON or bundle.

## Stop Conditions

Accept-before-validate, reusable ticket, caller identity, raw exceptions, or event drift blocks Phase 05.

## Commit Boundaries

- `feat(auth): add single-use websocket tickets`
- `feat(runtime): add fake live websocket flow`

## Next Artifacts

Session/ticket ports, accepted runtime stream, fake gateway, and integration fixtures.

## Exact File Manifest

- Create routes: `backend/app/api/routes/sessions.py`, `live.py`, `cards.py`, `health.py`.
- Create composition: `backend/app/api/dependencies.py`, `error_handlers.py`, `backend/app/main.py`.
- Create services: `session_service.py`, `ticket_service.py`, `live_runtime_service.py`, `card_service.py`.
- Create adapters: `app_websocket_ticket_issuer.py`, `fake_live_adapter.py`.
- Create repositories/ports: `session_store.py`, `ticket_use_store.py`, each with an in-memory test implementation scoped to this phase.
- Create tests: `backend/tests/integration/api/test_sessions.py`, `test_live_websocket.py`, `test_ticket_abuse.py`, `test_reconnect.py`, `test_card_confirm_recovery.py`.
- Create fixtures: `backend/tests/fixtures/clock.py`, `signing.py`, `runtime_streams.py`.
- Modify: `backend/app/core/config.py`, `constants.py`, `schemas/session_schemas.py`, `schemas/runtime_events.py` only when the normative wire shape is unchanged.
- Migration/seed: none. Cleanup: in-memory stores are disposed by the FastAPI lifespan fixture.

## Exact Public Signatures

```python
class AppWebSocketTicketIssuer(LiveCredentialIssuer[AppWebSocketGrant]):
    async def issue(
        self, request: CredentialIssueRequest, context: TrustedRequestContext
    ) -> AppWebSocketGrant: ...

class TicketVerifier(Protocol):
    async def verify_and_consume(
        self, encoded_ticket: SecretStr, expected_session_id: UUID, origin: str
    ) -> AppWebSocketTicketClaims: ...

class LiveRuntimeService:
    async def serve(
        self, websocket: WebSocketPort, context: TrustedRequestContext,
        *, last_seen_sequence: int | None
    ) -> None: ...
```

Claims are exactly `session_id`, `user_id`, `jti`, `purpose="live_websocket"`, `iss`, `aud`, `origin`, `iat`, `exp`, and `max_uses=1`. HTTP endpoints are `/api/sessions`, `/api/sessions/{session_id}/ticket`, `/api/sessions/{session_id}/end`, and `/api/cards/confirm`; the WebSocket is `/api/sessions/{session_id}/live`.

## Error and Close-Code Matrix

| Failure | HTTP/WS result | Retry |
|---|---|---|
| Missing, malformed, bad signature, expired | close `4401`, `TICKET_INVALID` | issue new ticket |
| Wrong origin/audience/purpose/session/user | close `4403`, `TICKET_SCOPE_INVALID` | no automatic retry |
| JTI replay/max uses | close `4409`, `TICKET_REPLAYED` | issue new ticket after audit |
| Missing/ended session | close `4410`, `SESSION_NOT_CONNECTABLE` | create or resume valid session |
| Sequence replay unavailable | `fallback.show: SESSION_RESUME_UNAVAILABLE` then close | start a new session |

The route validates Origin and atomically consumes the ticket before `accept()`. It reads no audio frame or command before that point.

## Executable TDD Ledger

| Cycle | RED file/test | Expected RED | Minimal GREEN |
|---|---|---|---|
| 04.1 | `test_sessions.py::test_ticket_cookie_is_http_only_strict_and_session_bound` | route 404 | session/ticket route plus issuer |
| 04.2 | `test_ticket_abuse.py::test_expired_ticket_closes_4401` | socket accepts or wrong code | verifier expiry mapping |
| 04.3 | parametrized `wrong_origin/audience/purpose/session/user_close_4403` | wrong code | scope validator |
| 04.4 | `test_ticket_replay_closes_4409` with two simultaneous connects | both connect | atomic `consume_once(jti)` |
| 04.5 | `test_live_websocket.py::test_valid_socket_emits_ready_before_reading_audio` | no event/order mismatch | fake Live runtime |
| 04.6 | `test_reconnect.py::test_replays_only_sequence_after_last_seen` | duplicate/gap | bounded event buffer |
| 04.7 | `test_card_confirm_recovery.py::test_http_and_ws_share_idempotent_service` | duplicated action | shared CardService call |

Representative complete RED:

```python
def test_ticket_replay_closes_4409(app_client: TestClient, ticket_cookie: str) -> None:
    with app_client.websocket_connect("/api/sessions/ses_1/live", cookies={"kk_live_ticket": ticket_cookie}):
        pass
    with pytest.raises(WebSocketDisconnect) as replay:
        with app_client.websocket_connect(
            "/api/sessions/ses_1/live", cookies={"kk_live_ticket": ticket_cookie}
        ):
            pass
    assert replay.value.code == 4409
```

Verify each RED with `backend/.venv/bin/pytest <file>::<test> -v`; the named assertion must fail. GREEN reruns focused plus `backend/.venv/bin/pytest backend/tests/integration/api -v`. REFACTOR may extract claim parsing and ports only; rerun unit, integration, ruff, and mypy.

## Checkpoint and Rollback

Expected checkpoint: all abuse cases return the fixed code, valid connection emits `session.ready`, and `scripts/check_no_secrets.py` passes against the bundle. Rollback removes the Phase 04 app/service/adapter files; it does not change specs or Phase 02 types. A socket accepted before validation, reusable JTI, or caller-provided identity is an immediate stop condition.

## Implementation Record

- Added FastAPI app composition, health/session/ticket/card/live routes, stable error mapping, and server-resolved synthetic development identity.
- Added JWT issuer/verifier with exact claims, injected clock, manual scope checks, and atomic in-memory JTI consumption before `accept()`.
- Added fake binary audio echo, deterministic `session.ready`/`audio.listening`, bounded session event history, replay after `last_seen_sequence`, visible stale-resume fallback, and shared HTTP/WS `CardService` idempotency.
- Added a frontend `BackendConversationRuntime` that requests the HttpOnly app ticket and maps backend snake_case events without exposing a credential.
- API/WebSocket integration coverage includes 17 cases for cookie policy, invalid/scope/replay/inactive close codes, ordering, binary flow, bounded reconnect replay/fallback, and recovery confirmation.
- No migration, database, Gemini call, MCP process, real TTS, or caller-supplied user identity was added.
- Automated backend/frontend and secret-scan checkpoints are green. Phase 03 responsive browser acceptance passed, so the dependent Phase 04 acceptance gate is released.
