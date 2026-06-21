# Kith&Kin MCP Tool Contracts

Version: 0.1.0
Status: Draft contract
Authority: `AGENTS.md` is authoritative when older draft documents conflict with this contract.

## 1. Purpose

This document defines the model-callable tools exposed by the Kith&Kin stdio MCP server. It is normative for agent prompts, `McpToolset` configuration, backend orchestration, tool traces, tests, and evals.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** describe requirement strength.

The MVP exposes exactly these four tools:

1. `memory_search(query, tags)`
2. `memory_write(key, value, tags)`
3. `check_drug_interaction(new_drug, current_meds)`
4. `notify_family(summary)`

No React component, browser hook, or frontend API module may call the MCP server directly. Calls MUST pass through the backend service and `McpToolAdapter` boundaries.

## 2. Trust Boundary and Execution Context

Tool arguments are model-controlled input and MUST be validated. Identity, authorization, consent, and destination information are trusted backend context and MUST NOT be accepted from model-callable arguments.

The backend adapter supplies this context through an implementation-private channel:

```json
{
  "request_id": "req_01JY7N3M6Q",
  "session_id": "ses_01JY7N2Z8H",
  "user_id": "usr_demo_parent_01",
  "actor": "companion",
  "guardian_decision_id": null,
  "confirmation_id": null,
  "idempotency_key": null
}
```

The exact context propagation mechanism is adapter-private. The following invariants are public:

- The browser and the model MUST NOT choose `user_id`, family destination, approval state, or confirmation state.
- The MCP server MUST reject write or external-action calls when required context is missing, expired, for another session, or already consumed.
- The MCP server MUST scope reads to the authenticated user's authorised profile.
- Parent profile health data MAY be returned to Companion for the authorised workflow. The same data MUST be redacted in logs and traces.

## 3. Permission and Caller Matrix

| Tool | Tier | Agent may propose | Backend executor | Guardian gate | Parent confirmation |
|---|---|---|---|---|---|
| `memory_search` | `read_only` | Companion, Guardian | `McpToolAdapter` | Guardian still inspects the turn | Not required after session consent |
| `check_drug_interaction` | `read_only` | Companion | `McpToolAdapter` | Guardian still inspects the turn and resulting cards | Not required |
| `memory_write` | `write_local` | Companion | `McpToolAdapter` after confirmation service | Required | Required |
| `notify_family` | `external_action` | Companion | `McpToolAdapter` after confirmation service | Required | Required |

Router MUST NOT call tools. Companion may propose write and external actions, but it MUST NOT bypass the backend confirmation workflow. Guardian is a policy gate, not an alternate executor.

## 4. Common Result and Error Contract

Expected outcomes use a typed result envelope. Invalid MCP framing may use a protocol error; validation, authorization, timeout, and provider failures MUST use this safe domain envelope.

```json
{
  "ok": true,
  "status": "success",
  "data": {},
  "error": null
}
```

```json
{
  "ok": false,
  "status": "unavailable",
  "data": null,
  "error": {
    "code": "MEMORY_UNAVAILABLE",
    "message": "Authorised memory is temporarily unavailable.",
    "retryable": true,
    "fallback_code": "memory_unavailable"
  }
}
```

Allowed `status` values are:

| Status | Meaning |
|---|---|
| `success` | The operation completed. |
| `no_result` | A read completed but found no authorised matching data. |
| `blocked` | Policy, confirmation, authorization, or idempotency rules prevented the action. |
| `validation_error` | Tool arguments were invalid. |
| `timeout` | The configured deadline elapsed. |
| `unavailable` | A required repository or provider was unavailable. |

Rules:

- `data` MUST be present only for `success` or `no_result`.
- `error` MUST be present for every non-success outcome except `no_result`.
- `error.message` MUST be safe for developer-facing diagnostics but MUST NOT contain raw provider output, credentials, contact details, identifiers, or health data.
- `fallback_code` is a stable machine value. MCP tools MUST NOT format UI messages.
- Read-only tools MAY retry once when the retry stays within the configured deadline.
- Write and external-action tools MUST NOT retry with a new idempotency key. A retry with the same key MUST return the stored outcome and MUST NOT repeat the side effect.

Default deadlines are configurable backend constants:

| Tool | Default deadline |
|---|---:|
| `memory_search` | 1500 ms |
| `check_drug_interaction` | 2500 ms |
| `memory_write` | 3000 ms |
| `notify_family` | 5000 ms |

## 5. `memory_search`

### 5.1 Purpose and invocation

`memory_search` retrieves authorised profile, medication, allergy, visit-history, or family-availability records. It is read-only.

At session start, the backend SHOULD prefetch profile context with:

```json
{
  "query": "profile",
  "tags": ["profile", "medications", "allergies"]
}
```

### 5.2 Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["query", "tags"],
  "properties": {
    "query": {"type": "string", "minLength": 1, "maxLength": 200},
    "tags": {
      "type": "array",
      "maxItems": 10,
      "uniqueItems": true,
      "items": {"type": "string", "minLength": 1, "maxLength": 40}
    }
  }
}
```

`tags` narrows the search. Supported MVP tags include `profile`, `medications`, `allergies`, `conditions`, `visit_summary`, `pharmacy`, and `follow_up`.

### 5.3 Success data

```json
{
  "ok": true,
  "status": "success",
  "data": {
    "records": [
      {
        "record_id": "mem_01JY7NE7QF",
        "key": "profile:medications",
        "value": {
          "current_medications": ["Lisinopril"]
        },
        "tags": ["profile", "medications"],
        "updated_at": "2026-06-22T09:30:00Z"
      }
    ]
  },
  "error": null
}
```

When no record matches, the server MUST return `ok: true`, `status: "no_result"`, and an empty `records` array. Companion MUST treat missing or unavailable memory as unknown and MUST NOT infer medication, allergy, identity, or family facts.

Success data schema:

| Field | Type | Required | Constraint |
|---|---|---:|---|
| `records` | array | Yes | Zero or more authorised records |
| `records[].record_id` | string | Yes | Opaque server identifier |
| `records[].key` | string | Yes | Authorised memory namespace and key |
| `records[].value` | object | Yes | Structured data; never raw audio or transcript |
| `records[].tags` | unique string array | Yes | Authorised classification tags |
| `records[].updated_at` | RFC 3339 timestamp | Yes | Last persisted update |

## 6. `memory_write`

### 6.1 Purpose and preconditions

`memory_write` stores a structured pharmacy visit summary for cross-session recall. It is not a generic transcript or profile mutation tool.

Before execution, all conditions MUST be true:

- Guardian approved the exact proposed summary.
- The parent reviewed the summary and explicitly confirmed saving it.
- The `confirmation_id` is session-bound, unexpired, and unused.
- The adapter supplies an idempotency key.

### 6.2 Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["key", "value", "tags"],
  "properties": {
    "key": {
      "type": "string",
      "pattern": "^visit_summary:[A-Za-z0-9_-]{1,64}$"
    },
    "value": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "mentioned_drugs",
        "pharmacist_advice_summary",
        "unresolved_questions",
        "follow_up_needed",
        "family_notification_requested"
      ],
      "properties": {
        "mentioned_drugs": {
          "type": "array",
          "maxItems": 20,
          "items": {"type": "string", "minLength": 1, "maxLength": 120}
        },
        "pharmacist_advice_summary": {"type": "string", "minLength": 1, "maxLength": 1000},
        "unresolved_questions": {
          "type": "array",
          "maxItems": 20,
          "items": {"type": "string", "minLength": 1, "maxLength": 300}
        },
        "follow_up_needed": {"type": "boolean"},
        "family_notification_requested": {"type": "boolean"}
      }
    },
    "tags": {
      "type": "array",
      "minItems": 1,
      "maxItems": 10,
      "uniqueItems": true,
      "contains": {"const": "visit_summary"},
      "items": {"type": "string", "minLength": 1, "maxLength": 40}
    }
  }
}
```

Raw audio, raw transcripts, card numbers, passport or Medicare numbers, addresses, and family contact details MUST NOT be stored through this tool.

### 6.3 Success and duplicate outcome

```json
{
  "ok": true,
  "status": "success",
  "data": {
    "memory_record_id": "mem_01JY7P3X8V",
    "version": 1,
    "written_at": "2026-06-22T10:05:00Z",
    "replayed": false
  },
  "error": null
}
```

A repeated call with the same idempotency key MUST return the original record and `replayed: true`. The server MUST NOT create another record. A reused key with different input MUST return `blocked` with `IDEMPOTENCY_CONFLICT`.

Success data schema:

| Field | Type | Required | Constraint |
|---|---|---:|---|
| `memory_record_id` | string | Yes | Opaque server identifier |
| `version` | integer | Yes | At least 1 |
| `written_at` | RFC 3339 timestamp | Yes | Server commit time |
| `replayed` | boolean | Yes | `true` only for an idempotent replay |

## 7. `check_drug_interaction`

### 7.1 Purpose and trigger

This read-only tool flags whether a specifically detected candidate medicine needs pharmacist confirmation against the current medication list. Companion MUST NOT call it for vague references such as “this medicine” when no drug name has been established. In that case, the safe path is to ask the pharmacist to write down or confirm the name.

### 7.2 Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["new_drug", "current_meds"],
  "properties": {
    "new_drug": {"type": "string", "minLength": 1, "maxLength": 120},
    "current_meds": {
      "type": "array",
      "maxItems": 50,
      "uniqueItems": true,
      "items": {"type": "string", "minLength": 1, "maxLength": 120}
    }
  }
}
```

### 7.3 Success data

```json
{
  "ok": true,
  "status": "success",
  "data": {
    "risk_level": "needs_pharmacist_confirmation",
    "reason_code": "potential_interaction_found",
    "matched_current_meds": ["Lisinopril"],
    "source_type": "demo_curated_data"
  },
  "error": null
}
```

Allowed `risk_level` values are `none`, `caution`, `needs_pharmacist_confirmation`, and `unknown`.

The result is decision support for generating a question. It MUST NOT claim that a medicine is safe or unsafe and MUST NOT instruct the parent to take, avoid, stop, or change a medicine. `unknown`, `timeout`, and `unavailable` MUST lead to pharmacist-confirmation fallback behaviour.

Success data schema:

| Field | Type | Required | Constraint |
|---|---|---:|---|
| `risk_level` | enum | Yes | `none`, `caution`, `needs_pharmacist_confirmation`, or `unknown` |
| `reason_code` | string | Yes | Stable non-prescriptive classification code |
| `matched_current_meds` | string array | Yes | Zero or more caller-supplied medication names |
| `source_type` | enum | Yes | `demo_curated_data` or `unknown` |

## 8. `notify_family`

### 8.1 Purpose and preconditions

`notify_family` sends the parent-approved visit summary to the authorised family destination. The destination is resolved server-side. The tool input MUST NOT accept a contact ID, phone number, email address, or arbitrary destination.

Before execution, all conditions MUST be true:

- Guardian approved the exact outbound summary.
- The parent saw exactly what will be sent and explicitly confirmed sending it.
- The authorised profile contains an available family destination.
- The `confirmation_id` and idempotency key are valid.

### 8.2 Input schema

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["summary"],
  "properties": {
    "summary": {
      "type": "object",
      "additionalProperties": false,
      "required": ["summary_zh", "mentioned_drugs", "unresolved_questions", "urgency"],
      "properties": {
        "summary_zh": {"type": "string", "minLength": 1, "maxLength": 1500},
        "mentioned_drugs": {
          "type": "array",
          "maxItems": 20,
          "items": {"type": "string", "minLength": 1, "maxLength": 120}
        },
        "unresolved_questions": {
          "type": "array",
          "maxItems": 20,
          "items": {"type": "string", "minLength": 1, "maxLength": 300}
        },
        "urgency": {"enum": ["normal", "follow_up_needed", "urgent"]}
      }
    }
  }
}
```

### 8.3 Success data

```json
{
  "ok": true,
  "status": "success",
  "data": {
    "notification_id": "ntf_01JY7Q1B6P",
    "sent_at": "2026-06-22T10:10:00Z",
    "replayed": false
  },
  "error": null
}
```

Notification failure MUST remain visible and retryable. It MUST NOT be reported as sent, and the system MUST preserve the reviewed summary for a safe retry or screenshot fallback.

Success data schema:

| Field | Type | Required | Constraint |
|---|---|---:|---|
| `notification_id` | string | Yes | Opaque provider-independent identifier |
| `sent_at` | RFC 3339 timestamp | Yes | Confirmed send time |
| `replayed` | boolean | Yes | `true` only when returning a prior idempotent outcome |

## 9. Error and Fallback Codes

| Code | Status | Retryable | Required behaviour |
|---|---|---:|---|
| `INVALID_TOOL_ARGUMENTS` | `validation_error` | No | Do not call the tool; surface a safe application error. |
| `AUTHORISED_CONTEXT_MISSING` | `blocked` | No | Block access; do not ask the model to invent identity context. |
| `MEMORY_NO_RESULT` | `no_result` | No | Treat facts as unknown and ask the pharmacist to confirm. |
| `MEMORY_UNAVAILABLE` | `unavailable` | Yes | Do not infer health history; use `memory_unavailable`. |
| `DRUG_NAME_REQUIRED` | `validation_error` | No | Ask the pharmacist to confirm or write down the drug name. |
| `DRUG_CHECK_UNAVAILABLE` | `unavailable` | Yes | Ask the pharmacist to check compatibility. |
| `GUARDIAN_APPROVAL_REQUIRED` | `blocked` | No | Do not execute the action. |
| `PARENT_CONFIRMATION_REQUIRED` | `blocked` | No | Show the confirmation UI; do not execute the action. |
| `CONFIRMATION_EXPIRED` | `blocked` | No | Render a fresh card set and confirmation flow. |
| `IDEMPOTENCY_CONFLICT` | `blocked` | No | Do not repeat or alter the side effect. |
| `FAMILY_DESTINATION_UNAVAILABLE` | `blocked` | No | Offer save or screenshot fallback. |
| `NOTIFICATION_UNAVAILABLE` | `unavailable` | Yes | Show retry; never report success. |
| `TOOL_TIMEOUT` | `timeout` | Tool-dependent | Follow the tool-specific safe fallback. |

## 10. Audit Trace Contract

Every tool attempt MUST produce one redacted trace event. Tool input and output summaries MUST be generated by explicit allowlists, not by logging and then regex-redacting the raw payload.

```json
{
  "event_type": "tool_call_event",
  "event_id": "evt_01JY7QAZJ4",
  "session_id": "ses_01JY7N2Z8H",
  "agent_name": "companion",
  "tool_name": "check_drug_interaction",
  "permission_tier": "read_only",
  "input_redacted": {
    "candidate_drug_present": true,
    "current_medication_count": 1
  },
  "output_redacted": {
    "risk_level": "needs_pharmacist_confirmation"
  },
  "guardian_decision_id": "gdn_01JY7Q8F0C",
  "confirmation_id": null,
  "status": "success",
  "latency_ms": 182,
  "pii_redacted": true,
  "timestamp": "2026-06-22T10:09:30Z"
}
```

Traces MUST NOT contain raw memory values, medication names, health summaries, family contact details, payment data, identity numbers, addresses, API keys, or provider debug output.

## 11. Forbidden Behaviour

The implementation MUST NOT:

- expose MCP transport or credentials to React;
- accept caller-supplied user identity or notification destination;
- allow Router to execute tools;
- call `check_drug_interaction` without a concrete drug entity;
- treat a fuzzy drug-name match as fact without a pharmacist-confirmation card;
- run `memory_write` or `notify_family` before Guardian approval and parent confirmation;
- use write or external-action retries that can duplicate a side effect;
- store raw audio or raw conversation transcripts through `memory_write`;
- turn interaction-check output into direct medical advice; or
- log raw tool arguments or results.

## 12. Legacy and Compatibility Mapping

| Legacy draft term | Canonical MVP contract | Resolution |
|---|---|---|
| `memory.search` | `memory_search` | Rename all implementations, prompts, traces, and eval fixtures. |
| `memory.write` | `memory_write` | Rename all implementations, prompts, traces, and eval fixtures. |
| `knowledge.lookup` / `knowledge_lookup` | No MCP tool | Out of scope. Ask the pharmacist to confirm or write down an unknown drug name. |
| Frontend calls MCP | Backend service calls `McpToolAdapter` | Direct frontend access is forbidden. |
| Model supplies `user_id` or family destination | Backend execution context | Identity and destination are never model-controlled. |

This compatibility table intentionally overrides the older draft architecture and eval vocabulary. Those source documents must be reconciled before implementation is considered complete.
