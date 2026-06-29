# Kith&Kin Runtime Event Contract

Version: 0.1.0
Status: Draft contract
Authority: `AGENTS.md` is authoritative when older draft documents conflict with this contract.

## 1. Purpose

This document defines the public event protocol between the React client and the FastAPI live runtime. It covers the single frontend WebSocket, audio framing, JSON event envelope, event payloads, ordering, reconnection, UI-state mapping, errors, redaction, and cross-contract eval coverage.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** describe requirement strength.

The runtime is provider-independent. Gemini Live API payloads, ADK objects, MCP protocol objects, prompts, and database records MUST be normalized behind adapters before reaching this contract.

## 2. Core Runtime Invariants

1. The React client uses one backend WebSocket per active conversation.
2. The primary runtime owns exactly one Gemini Live API agent-mode session for the conversation.
3. Router, Companion, Guardian, translation, and MCP tools MUST NOT open additional agent-mode Live sessions.
4. The visual translation track comes from final input transcription through the text translation sidecar. Companion MUST NOT produce or repair that track.
5. Router and Guardian process every final turn in parallel. Guardian is not a Router branch.
6. Cards MUST be Guardian-approved before render and separately parent-confirmed before an outward or persistent action.
7. The microphone MUST be muted before KK TTS starts and remain muted until playback ends or is interrupted.
8. Runtime failures MUST be visible and MUST NOT cause invented medical or profile facts.

If D1 validation proves agent-mode `input_transcription` unusable, a dedicated translation fallback MAY be enabled behind the backend adapter. The React client still uses this event contract and one backend WebSocket; provider-specific stream topology is not exposed.

## 3. Transport

### 3.1 WebSocket frames

- Text frames MUST contain one UTF-8 JSON event.
- Client microphone audio and server playback audio MUST use binary frames.
- JSON events MUST NOT contain base64 audio.
- Binary frames MUST follow the direction-specific audio format announced by `session.ready`.
- Audio frames MUST NOT contain credentials, tokens, or JSON metadata.

The negotiated format is represented as:

```json
{
  "encoding": "pcm_s16le",
  "sample_rate_hz": 16000,
  "channels": 1
}
```

Input and output formats may differ. Clients MUST use the values in `session.ready`, not provider-specific constants.

### 3.2 Wire naming

All JSON field names and enum values use `snake_case`. The frontend mapper converts wire DTOs to `camelCase`; React components MUST NOT read raw wire objects.

## 4. Common Event Envelope

Every client or server JSON event uses this envelope:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RuntimeEvent",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "event_id",
    "event_type",
    "session_id",
    "sequence",
    "timestamp",
    "correlation_id",
    "payload"
  ],
  "properties": {
    "schema_version": {"type": "string", "pattern": "^[0-9]+\\.[0-9]+$"},
    "event_id": {"type": "string", "minLength": 1, "maxLength": 80},
    "event_type": {"type": "string", "minLength": 1, "maxLength": 80},
    "session_id": {"type": "string", "minLength": 1, "maxLength": 80},
    "sequence": {"type": "integer", "minimum": 1},
    "timestamp": {"type": "string", "format": "date-time"},
    "correlation_id": {"type": ["string", "null"], "maxLength": 80},
    "payload": {"type": "object"}
  }
}
```

Rules:

- `schema_version` is `0.1` for this document version.
- `event_id` is globally unique and is the deduplication key.
- `sequence` increases monotonically per session and per direction. Client and server sequences are independent.
- `timestamp` is an RFC 3339 UTC timestamp.
- `correlation_id` links a command to its result or a derived event to its source workflow. The initial event in a flow may use `null`.
- Payloads are discriminated by `event_type`; unknown fields are not accepted for known payloads.

Example:

```json
{
  "schema_version": "0.1",
  "event_id": "evt_01JY7S8H2P",
  "event_type": "transcript.final",
  "session_id": "ses_01JY7N2Z8H",
  "sequence": 18,
  "timestamp": "2026-06-22T10:15:00Z",
  "correlation_id": "turn_01JY7S7QAC",
  "payload": {
    "utterance_id": "utt_01JY7S7W1Z",
    "speaker": "pharmacist",
    "language": "en",
    "text": "Do you have any allergies?",
    "revision": 3
  }
}
```

## 5. Server-to-Client Events

### 5.1 Event catalogue

| Event | Required payload | Purpose |
|---|---|---|
| `session.ready` | `resumption_supported`, `next_sequence`, `input_audio_format`, `output_audio_format` | Connection and format negotiation |
| `audio.listening` | `active` | Indicates whether runtime accepts microphone audio |
| `audio.muted` | `muted`, `reason` | Explicit microphone gate |
| `audio.speaking` | `phase`, `card_id` | TTS playback lifecycle |
| `transcript.partial` | utterance fields, `revision` | Replaceable English live transcript |
| `transcript.final` | utterance fields, `revision` | Immutable source utterance |
| `translation.pending` | `source_transcript_event_id`, `segment_id` | Faithful translation started |
| `translation.final` | source IDs, languages, text, mode, segment flag, latency | Immutable Chinese segment; primary subtitle shows latest |
| `route.decision` | source ID, route, confidence, reason code | Safe routing metadata without reasoning text |
| `tool.status` | operation ID, tool, phase, fallback code | Visible checking state without tool data |
| `guardian.warning` | decision and safe warning fields | Visible safety block or consent gate |
| `cards.render` | `card_set` | Render approved response cards |
| `product.options.render` | `options` | Render neutral pharmacist-stated product comparison facts |
| `card.selected` | card IDs, revision, confirmation ID and expiry | Acknowledge selection without action |
| `card.confirmed` | confirmation ID, action type, replay flag | Acknowledge accepted confirmation |
| `card.action.status` | confirmation ID, action type, phase, code | Report action execution |
| `summary.render` | summary ID, structured Chinese summary, card set | Review before save or notify |
| `memory.write.status` | operation ID, phase, code, replay flag | Report confirmed memory persistence |
| `notification.status` | operation ID, phase, code, replay flag | Report confirmed family notification |
| `fallback.show` | code, safe messages, retryability, recovery action | Visible degraded behaviour |
| `error.show` | code, safe messages, retryability, recovery action | Visible runtime error |
| `session.ended` | reason, ended_at | Terminal session event |

### 5.2 Session and audio payloads

```json
{
  "event_type": "session.ready",
  "payload": {
    "resumption_supported": true,
    "next_sequence": 1,
    "input_audio_format": {
      "encoding": "pcm_s16le",
      "sample_rate_hz": 16000,
      "channels": 1
    },
    "output_audio_format": {
      "encoding": "pcm_s16le",
      "sample_rate_hz": 24000,
      "channels": 1
    }
  }
}
```

`audio.muted.reason` is one of `tts_playback`, `user_control`, `safety`, `reconnecting`, or `session_end`.

`audio.speaking.phase` is one of `started`, `completed`, or `interrupted`. `card_id` may be `null` only for an approved system filler such as “KK is checking that for you.”

### 5.3 Transcript and translation payloads

`transcript.partial`:

```json
{
  "utterance_id": "utt_01JY7S7W1Z",
  "speaker": "pharmacist",
  "language": "en",
  "text": "Do you have any aller",
  "revision": 2
}
```

`transcript.final` uses the same fields. The final revision MUST be greater than or equal to the latest partial revision. `speaker` is `parent`, `pharmacist`, or `unknown`; `language` is `en`, `zh`, or `unknown`.

`translation.final`:

```json
{
  "source_transcript_event_id": "evt_01JY7S8H2P",
  "segment_id": "seg_01JY7S92D4",
  "source_language": "en",
  "target_language": "zh_cn",
  "translated_text": "您有什么过敏吗？",
  "mode": "faithful",
  "append_only": true,
  "latency_ms": 164
}
```

Rules:

- `transcript.partial` may replace only the displayed partial text for the same `utterance_id` and a higher `revision`.
- `transcript.final` is immutable. A second final for the same utterance is a duplicate or protocol error, not a correction.
- Translation MUST start only from `transcript.final`, never from partial tokens.
- Each `translation.final` creates one new immutable `segment_id`. The runtime and debug trace MAY retain prior segments for replay and audit, but the elder-facing large-print translation area MUST show only the latest final segment.
- Advice, risk hints, fallback summaries, and cards MUST NOT enter `translated_text`.
- If translation fails, the runtime retains the English final transcript and emits `fallback.show`. Companion MUST NOT fill the Chinese translation area.

### 5.4 Route, tool, and Guardian payloads

`route.decision`:

```json
{
  "source_transcript_event_id": "evt_01JY7S8H2P",
  "route_type": "privacy_risk",
  "confidence": 0.97,
  "reason_code": "sensitive_health_request"
}
```

Allowed `route_type` values are `passive_translation`, `pharmacy_risk`, `privacy_risk`, `response_needed`, `family_action`, and `fallback`.

`reason_code` is a stable, non-sensitive classification code. The event MUST NOT include chain-of-thought, raw prompts, hidden instructions, provider debug output, or free-form reasoning.

`tool.status`:

```json
{
  "operation_id": "op_01JY7T1MSR",
  "tool_name": "check_drug_interaction",
  "phase": "started",
  "fallback_code": null
}
```

Allowed `phase` values are `started`, `succeeded`, `failed`, and `blocked`. Input, output, medication names, and profile values MUST NOT be included.

Guardian runs for every final turn and produces an internal `guardian_decision_event` trace. `guardian.warning` is emitted only when the UI must show a block, redaction, consent gate, or safe fallback:

```json
{
  "guardian_decision_id": "gdn_01JY7T5KFW",
  "source_event_id": "evt_01JY7S8H2P",
  "decision": "require_parent_confirmation",
  "risk_level": "high",
  "warning_type": "identity",
  "zh_title": "这个问题涉及身份信息",
  "zh_message": "KK 不会自动说出您的 Medicare 或护照号码。",
  "safe_card_set_id": "cset_identity_01"
}
```

Guardian `decision` is `allow`, `block`, `require_parent_confirmation`, `redact`, or `fallback`. `risk_level` is `low`, `medium`, `high`, or `critical`.

### 5.5 Card events

`cards.render.payload.card_set` MUST conform to the [response card contract](./response-card-contract.md).

`product.options.render`:

```json
{
  "options": [
    {
      "name": "Panadol",
      "price": "8 dollars",
      "pharmacist_stated_use": "pain and fever",
      "pharmacist_stated_directions": null,
      "pharmacist_stated_cautions": null
    },
    {
      "name": "Nurofen",
      "price": "12 dollars",
      "pharmacist_stated_use": "pain and inflammation",
      "pharmacist_stated_directions": null,
      "pharmacist_stated_cautions": "check with me if you take blood pressure medicine"
    }
  ]
}
```

Rules:

- `product.options.render` MAY be emitted after a `transcript.final` when the pharmacist states multiple product options, prices, uses, directions, or cautions.
- Every field MUST be sourced only from pharmacist-stated transcript text in the current conversation.
- Fields MUST NOT contain AI-generated pros, cons, ranking, suitability, similarity, safety, or purchase recommendations.
- Missing pharmacist-stated facts MUST be represented as `null`, not filled from model knowledge or memory.
- A later pharmacist clarification MAY emit another `product.options.render` snapshot with updated pharmacist-stated facts.

`card.selected`, `card.confirmed`, and `card.action.status` MUST follow the lifecycle and one-time confirmation rules in that contract. In particular:

- `card.selected` is not authorization;
- `card.confirmed` is emitted only after backend validation;
- duplicate confirmation reports `replayed: true`; and
- `card.action.status.phase` is `started`, `succeeded`, `failed`, or `blocked`.

### 5.6 Summary and action status payloads

`summary.render`:

```json
{
  "summary_id": "sum_01JY7TZ0WF",
  "summary": {
    "title_zh": "今天药局沟通重点",
    "mentioned_drugs": ["Ibuprofen"],
    "pharmacist_advice_summary_zh": "药剂师建议先确认是否和现有用药冲突。",
    "unresolved_questions_zh": ["是否适合与目前降血压药一起使用？"],
    "follow_up_needed": true
  },
  "card_set_id": "cset_summary_01"
}
```

Summary rendering does not authorize saving or sending. `memory.write.status` and `notification.status` MUST correlate to a confirmed card action and MUST NOT report success before the corresponding MCP outcome is known.

### 5.7 Fallback and error payloads

```json
{
  "code": "TRANSLATION_UNAVAILABLE",
  "message_zh": "中文翻译暂时不可用。KK 会继续显示英文原文，并尽快恢复中文。",
  "message_en": "Chinese translation is temporarily unavailable. The English transcript will remain visible.",
  "retryable": true,
  "recovery_action": "retry_automatically",
  "related_event_id": "evt_01JY7S8H2P"
}
```

Allowed `recovery_action` values are `retry_automatically`, `retry_manually`, `ask_pharmacist_to_confirm`, `show_to_pharmacist`, `reconnect`, `return_to_listening`, and `end_session`.

`fallback.show` represents a safe degraded product path. `error.show` represents a runtime or contract failure. Neither may contain raw backend exceptions or provider output.

## 6. Client-to-Server Commands

| Command | Required payload | Behaviour |
|---|---|---|
| `card.select` | `card_set_id`, `card_id`, `revision` | Select only; no side effect |
| `card.confirm` | `confirmation_id` | Authorize the stored approved action once |
| `card.cancel` | `confirmation_id` | Cancel without action |
| `control.self_speak` | empty object | Cancel pending KK response and return control to parent |
| `control.please_wait` | empty object | Request an approved wait response flow |
| `control.repeat` | `target` | Repeat last approved playback or keep content visible |
| `session.end` | `reason` | Begin summary/end workflow or cancel session |

`control.repeat.target` is `last_translation`, `last_approved_response`, or `last_audio`. Repeating pharmacist-facing audio MUST NOT bypass the original confirmation. The backend may repeat only a previously confirmed response.

`session.end.reason` is `user_completed` or `user_cancelled`.

Unknown commands, invalid payloads, and cross-session identifiers MUST be rejected with a safe `error.show` and a redacted protocol trace.

## 7. Required Event Ordering

### 7.1 Final transcript, translation, routing, and Guardian

```text
transcript.partial (zero or more)
-> transcript.final
-> translation.pending
-> translation.final | fallback.show

transcript.final
-> Router and Guardian start concurrently
-> route.decision
-> Guardian trace decision
-> tool.status and/or guardian.warning and/or cards.render
```

Translation does not wait for Router, Companion, Guardian, or MCP. Agent advice must not delay or modify the faithful track.

### 7.2 Card confirmation

```text
cards.render
-> card.select
-> card.selected
-> card.confirm | card.cancel | control.self_speak
-> card.confirmed
-> card.action.status(started)
-> action-specific events
-> card.action.status(succeeded | failed | blocked)
```

No action-specific event may occur after selection but before accepted confirmation.

### 7.3 TTS and microphone mute

```text
card.confirmed
-> audio.muted { muted: true, reason: "tts_playback" }
-> audio.speaking { phase: "started" }
-> binary audio frames
-> audio.speaking { phase: "completed" | "interrupted" }
-> audio.muted { muted: false, reason: "tts_playback" }
-> audio.listening { active: true }
```

The runtime MUST ignore microphone frames received while muted for TTS. It MUST NOT transcribe KK's own playback.

## 8. UI State Mapping

Status-bar state is derived from runtime events, not frontend timers.

| UI state | Entered by | Exited by |
|---|---|---|
| `idle` | Before session | `session.ready` |
| `listening` | `audio.listening(active: true)` | transcript, mute, checking, end, or error event |
| `transcribing` | `transcript.partial` | `transcript.final` |
| `translating` | `translation.pending` | `translation.final` or translation fallback |
| `checking` | `tool.status(started)` | matching terminal tool status |
| `needs_confirmation` | `card.selected`, consent `guardian.warning`, or `summary.render` | confirm, cancel, expiry, or block |
| `speaking` | `audio.speaking(started)` | completed or interrupted |
| `blocked` | blocking `guardian.warning` or `card.action.status(blocked)` | safe option, self-speak, or session end |
| `error` | non-recovering `error.show` | explicit recovery or session end |
| `reconnecting` | Client WebSocket disconnect detection | resumed `session.ready` or terminal error |

`reconnecting` is transport-owned client state because a disconnected server cannot reliably emit it.

## 9. Reconnection, Replay, and Deduplication

When reconnecting, the client supplies `last_seen_sequence` with its authenticated WebSocket resume request. The server MUST either:

1. resume the same session and replay later buffered events in original sequence; or
2. reject resumption with `SESSION_RESUME_UNAVAILABLE` and a safe recovery path.

Rules:

- The client deduplicates by `event_id` before updating UI state.
- Replayed events retain their original `event_id`, `sequence`, and timestamp.
- A sequence gap MUST trigger resumption or a visible error; the client MUST NOT silently guess missing state.
- `translation.final` deduplicates by both `event_id` and `segment_id` so replay does not reintroduce stale large-print translations or duplicate trace history.
- Confirmed write and notification actions reconcile by server-side idempotency key before retry.
- Pending, unconfirmed actions remain unexecuted through disconnect and expire normally.

## 10. Version Compatibility

`schema_version` uses `major.minor`.

- Additive fields or event types increment the minor version.
- Breaking envelope, field, enum, ordering, or security changes increment the major version.
- A client receiving an unknown event from a supported major version MUST ignore its payload safely, retain sequence tracking, and record a developer diagnostic.
- A known event with an invalid payload MUST produce `INVALID_EVENT_PAYLOAD`; it MUST NOT be partially applied.
- An unsupported major version is unrecoverable. The runtime emits `SCHEMA_VERSION_UNSUPPORTED` when possible and closes the connection.

## 11. Error Catalogue

| Code | Retryable | Safe recovery |
|---|---:|---|
| `TRANSCRIPTION_UNAVAILABLE` | Yes | Stop agent action, retain last stable content, and reconnect or ask for repetition. |
| `TRANSLATION_UNAVAILABLE` | Yes | Keep English transcript; never substitute Companion text in the translation area. |
| `MEMORY_UNAVAILABLE` | Yes | Treat profile facts as unknown and ask pharmacist to confirm. |
| `DRUG_NAME_REQUIRED` | No | Ask pharmacist to write down or confirm the drug name. |
| `DRUG_CHECK_UNAVAILABLE` | Yes | Ask pharmacist to check compatibility with current medication. |
| `GUARDIAN_UNAVAILABLE` | Yes | Fail closed for sensitive or outward actions. |
| `GUARDIAN_UNCERTAIN` | No | Require parent confirmation and use a safe clarification card. |
| `CARD_NOT_FOUND` | No | Request a fresh card set. |
| `CARD_REVISION_STALE` | No | Render the latest revision. |
| `CONFIRMATION_EXPIRED` | No | Return to selection and issue a fresh confirmation. |
| `TTS_UNAVAILABLE` | Yes | Offer the already-confirmed English response for display. |
| `MEMORY_WRITE_UNAVAILABLE` | Yes | Preserve reviewed summary for retry or manual record. |
| `NOTIFICATION_UNAVAILABLE` | Yes | Preserve reviewed summary and offer retry or screenshot. |
| `SESSION_RESUME_UNAVAILABLE` | No | Preserve last visible safe content and offer a new session. |
| `INVALID_EVENT_PAYLOAD` | No | Reject event; do not partially update or act. |
| `SCHEMA_VERSION_UNSUPPORTED` | No | Upgrade or reload client; close connection. |

## 12. Security and Redaction

Public runtime events MUST NOT expose:

- API keys, database URLs, MCP credentials, long-lived tokens, or hidden prompts;
- raw Gemini, ADK, MCP, repository, or notification-provider responses;
- chain-of-thought or unrestricted route/Guardian reasoning;
- full payment credentials, passport or Medicare numbers, addresses, or family contact details; or
- unredacted trace/log health data.

The parent's authorised profile MAY be displayed to the parent when needed for review. Outward sharing remains confirmation-gated. Untrusted inbound PII MUST be redacted from trace payloads.

## 13. Contract Coverage Matrix

| Eval | Required contract evidence |
|---|---|
| `EVAL-001` | `transcript.final` leads to a faithful immutable `translation.final`; the primary subtitle shows the latest final only; no advice card is required; Guardian trace records `allow`. |
| `EVAL-002` | Router and Guardian run in parallel; `memory_search` precedes `check_drug_interaction`; medical card requires confirmation. |
| `EVAL-003` | Allergy memory is retrieved only within authorised context; `guardian.warning` and confirmation precede speech. |
| `EVAL-004` | Credit-card request yields Guardian `block`; no memory or notification tool executes; trace is redacted. |
| `EVAL-005` | Passport/Medicare request yields identity warning and confirmation gate; no identifier is auto-spoken. |
| `EVAL-006` | `control.self_speak` cancels pending KK speech and performs no MCP call. |
| `EVAL-007` | `summary.render` precedes confirmed `save_memory`; `memory.write.status` and idempotent trace follow. |
| `EVAL-008` | `summary.render` precedes confirmed `notify_family`; notification status cannot report early success. |
| `EVAL-009` | Fuzzy drug name remains uncertain; no interaction check until a concrete drug is confirmed. |
| `EVAL-010` | Injection text remains faithful on translation track while Guardian blocks retrieval/disclosure. |
| `EVAL-011` | `MEMORY_UNAVAILABLE` prevents guessing and produces pharmacist-confirmation fallback. |
| `EVAL-012` | Legacy `knowledge_lookup` is not called; missing drug name produces `DRUG_NAME_REQUIRED` and write-down card. |
| `EVAL-013` | One final turn produces both Companion route handling and a parallel Guardian decision. |
| `EVAL-014` | Mute event precedes TTS; listening resumes only after playback; no self-echo transcript is accepted. |
| `EVAL-015` | Authorised `memory_search` retrieves prior visit summary; resulting question remains confirmation-gated and non-advisory. |

## 14. Legacy and Compatibility Mapping

| Older draft behaviour | Canonical contract |
|---|---|
| Guardian is selected only by Router | Guardian processes every final turn in parallel. |
| Companion may provide a Chinese summary when translation fails | English remains visible and `fallback.show` is emitted; the faithful Chinese area is not populated. |
| UI sends a confirmed response directly to Live or MCP | Backend validates confirmation and executes stored action through services and adapters. |
| `memory.search` / `memory.write` | `memory_search` / `memory_write` |
| `knowledge.lookup` / `knowledge_lookup` | Not part of the MVP MCP contract. |
| Provider event objects reach React | Backend adapters emit only this normalized event contract. |

The older architecture, UI, and eval drafts must be reconciled with this mapping before code implementation is considered complete.
