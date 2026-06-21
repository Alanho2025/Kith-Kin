# Phase 90: Client-Direct Gemini Live Migration Plan

Status: inactive future plan

## Goal

Migrate only after a runtime-contract major-version approval to browser→Gemini Live while preserving app-ticket-protected backend RAG/MCP/Guardian access.

## Non-Goals

Not part of MVP. Do not create issuer code, environment variables, dependencies, or capability claims now.

## Source of Truth

Future approved runtime spec, official Gemini ephemeral-token and Live function-calling contracts.

## Previous Phase Artifacts

Completed local backend-proxy product and an approved migration RFC.

## Entry Conditions

- Runtime spec major version approved.
- Threat model approved.
- Client-direct transcription/function-call spike passes.
- Backend RAG gateway and app ticket remain operational.

## Exit Checkpoint

Two credential types are non-interchangeable and the complete client-direct flow passes security, contract and latency gates.

## Files

Future create: `GeminiEphemeralGrant`, issuer adapter, frontend Gemini Live adapter, backend function-call relay, separate tests/fixtures. Modify runtime spec before code.

## Public Contracts

- Gemini grant audience is Gemini Live constrained v1alpha and never Kith&Kin API.
- App grant audience remains `kithkin-live-ws`/backend gateway and never Gemini.
- Browser relay accepts only `tool_call_id`, allowlisted tool name and validated arguments.
- Backend resolves identity/destination, applies Guardian/RAG/redaction, and returns correlated FunctionResponse.

## Required TDD Cycles

1. Gemini token rejected by every Kith&Kin API.
2. App ticket rejected by Gemini adapter.
3. Wrong audience/purpose cannot be cast or decoded as the other grant.
4. Gemini token is single-use with short creation expiry and server-controlled constraints.
5. Browser cannot add identity, destination, or unapproved tool.
6. FunctionResponse is bounded, redacted, Guardian-reviewed and correlated.
7. Backend outage/timeout returns safe function error without guessed data.

## Migration and Rollback

Feature flag changes topology only after dual-path staging. Rollback returns all sessions to backend proxy and revokes Gemini grant issuance. No mixed session may change topology mid-call.

## Stop Conditions

Do not start from this file alone. Missing major spec, threat model, spike, or human approval blocks all implementation.

## Suggested Commit Boundaries

- `docs(live): approve client-direct runtime contract`
- `feat(auth): add constrained Gemini ephemeral grants`
- `feat(live): add client-direct function relay`

## Artifacts Exposed After Migration

Versioned client-direct runtime, separate credential issuers, secured function relay and rollback evidence.

## Exact Future File Manifest

- First modify `specs/runtime-event-contract.md` with an approved breaking major version and add a signed architecture decision record.
- Then create `backend/app/domain/gemini_credentials.py`, `backend/app/adapters/gemini_ephemeral_token_issuer.py`, `backend/app/services/live_function_relay.py`.
- Create `frontend/src/features/conversation/runtime/GeminiDirectRuntime.ts` and `functionCallRelay.ts`.
- Create contract tests `backend/tests/contract/test_credential_non_interchangeability.py`, `test_function_relay.py`, `frontend/src/features/conversation/runtime/GeminiDirectRuntime.test.ts`.
- Create separate sanitised Gemini token/function-call fixtures. Add environment names only after code is active and documented.
- Migration: none unless the approved RFC requires new audit metadata; no speculative table is allowed.

## Exact Type Separation and Errors

```python
@dataclass(frozen=True)
class GeminiEphemeralGrant:
    encoded_token: SecretStr
    expires_at: datetime
    new_session_expires_at: datetime
    model: str
    api_version: Literal["v1alpha"]

class GeminiEphemeralTokenIssuer(LiveCredentialIssuer[GeminiEphemeralGrant]):
    async def issue(
        self, request: GeminiGrantRequest, context: TrustedRequestContext
    ) -> GeminiEphemeralGrant: ...

class LiveFunctionRelay:
    async def execute(
        self, request: RelayedFunctionCall, context: TrustedRequestContext
    ) -> RedactedFunctionResponse: ...
```

`AppWebSocketGrant` and `GeminiEphemeralGrant` share no inheritance beyond the generic protocol result position. Codes are `GRANT_AUDIENCE_INVALID`, `GRANT_PURPOSE_INVALID`, `GEMINI_GRANT_REPLAYED`, `FUNCTION_TOOL_NOT_ALLOWED`, `FUNCTION_ARGUMENT_INVALID`, `FUNCTION_SCOPE_INVALID`, `FUNCTION_GUARDIAN_BLOCKED`, and `FUNCTION_TIMEOUT`.

## Executable TDD Ledger

| Cycle | RED | Required assertion | GREEN |
|---|---|---|---|
| 90.1 | app API contract test presents Gemini token | every backend API rejects it | separate verifier/audience |
| 90.2 | Gemini adapter test presents app ticket | adapter rejects before network | separate TypeScript/Python types |
| 90.3 | single-use/creation-expiry tests | replay/late session accepted | constrained issuer |
| 90.4 | relay caller supplies user/destination | validation rejects fields | allowlisted relay DTO |
| 90.5 | Guardian block fixture | no backend tool executes | policy gate before adapter |
| 90.6 | oversized RAG response | bounded/redacted response only | existing RAG limiter |
| 90.7 | backend timeout | correlated safe function error | timeout mapping |

Complete non-interchangeability RED:

```python
@pytest.mark.asyncio
async def test_gemini_grant_cannot_authorise_backend_api(api_client, gemini_grant):
    response = await api_client.get(
        "/api/sessions/ses_1", headers={"Authorization": f"Bearer {gemini_grant.raw_for_test}"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "GRANT_AUDIENCE_INVALID"
```

Each RED uses a complete fake of the external Gemini token endpoint; no mock asserts its own call configuration. GREEN reruns the focused contract and the entire backend-proxy regression. Rollout is a server-controlled flag fixed for a session; rollback disables issuance, revokes outstanding grants, and returns new sessions to backend proxy. No mixed topology within an active session.

## Inactive Stop Checkpoint

This phase remains inactive until the major spec, threat model, provider spike, and explicit owner approval all exist. The current repository must not contain its environment variables or issuer implementation. Merely defining `LiveCredentialIssuer[TGrant]` does not claim client-direct support.
