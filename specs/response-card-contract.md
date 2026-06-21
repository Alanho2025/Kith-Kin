# Kith&Kin Response Card Contract

Version: 0.1.0
Status: Draft contract
Authority: `AGENTS.md` is authoritative when older draft documents conflict with this contract.

## 1. Purpose

This document defines the response-card data model, Guardian approval requirements, parent-confirmation protocol, lifecycle, side-effect rules, and safe content constraints for Kith&Kin.

The key words **MUST**, **MUST NOT**, **SHOULD**, **SHOULD NOT**, and **MAY** describe requirement strength.

Response cards help the parent decide what KK should say, show, save, or send. A rendered or selected card is never authorization. KK MUST NOT speak for the parent, display a response to the pharmacist, write memory, or notify family until the required confirmation has been accepted by the backend.

## 2. Ownership and Trust Boundary

- Companion proposes cards.
- Guardian reviews every proposed card before it is rendered.
- The backend stores the approved card set and owns its lifecycle.
- React renders server-provided display fields and sends identifiers only.
- React MUST NOT send executable text, action arguments, risk levels, approval flags, or sensitive payloads back as authority.
- The backend MUST execute the stored, approved card revision. It MUST reject stale, altered, expired, cross-session, or unapproved references.

`我自己说` is an escape control, not a response card. It is defined as `control.self_speak` in the runtime event contract and may take effect immediately because it makes KK stop acting; it does not speak, disclose, write, or notify.

## 3. Canonical Types

### 3.1 Response card

Wire JSON uses `snake_case`. Frontend mappers convert it to `camelCase` view models.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ResponseCard",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "card_id",
    "card_type",
    "zh_text",
    "en_text",
    "risk_level",
    "action",
    "requires_parent_confirmation",
    "requires_guardian_approval",
    "guardian_decision_id"
  ],
  "properties": {
    "card_id": {"type": "string", "minLength": 1, "maxLength": 80},
    "card_type": {
      "enum": [
        "ask_question",
        "confirm_info",
        "refuse_sensitive_request",
        "ask_to_write_down",
        "memory_action",
        "family_action"
      ]
    },
    "zh_text": {"type": "string", "minLength": 1, "maxLength": 120},
    "en_text": {"type": "string", "minLength": 1, "maxLength": 240},
    "risk_level": {"enum": ["normal", "caution", "privacy", "medical", "urgent"]},
    "action": {
      "type": "object",
      "additionalProperties": false,
      "required": ["type"],
      "properties": {
        "type": {
          "enum": ["speak", "show_to_pharmacist", "save_memory", "notify_family", "no_action"]
        }
      }
    },
    "requires_parent_confirmation": {"type": "boolean"},
    "requires_guardian_approval": {"type": "boolean"},
    "guardian_decision_id": {"type": "string", "minLength": 1, "maxLength": 80}
  }
}
```

Field rules:

- `zh_text` is the primary parent-facing text.
- `en_text` is the exact back-translation or action summary the parent reviews. For `speak` and `show_to_pharmacist`, it is the exact approved pharmacist-facing content.
- `action` contains only an action type. Tool arguments and sensitive values MUST remain in backend-owned pending-action state.
- `requires_guardian_approval` MUST be `true` for every generated card.
- `requires_parent_confirmation` MUST be `true` for `speak`, `show_to_pharmacist`, `save_memory`, and `notify_family`.
- `no_action` MAY set `requires_parent_confirmation` to `false`, but it MUST NOT trigger TTS, outward display, persistence, or an external action.

### 3.2 Card set

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "CardSet",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "card_set_id",
    "revision",
    "source_event_id",
    "generated_at",
    "expires_at",
    "cards"
  ],
  "properties": {
    "card_set_id": {"type": "string", "minLength": 1, "maxLength": 80},
    "revision": {"type": "integer", "minimum": 1},
    "source_event_id": {"type": "string", "minLength": 1, "maxLength": 80},
    "generated_at": {"type": "string", "format": "date-time"},
    "expires_at": {"type": "string", "format": "date-time"},
    "cards": {
      "type": "array",
      "minItems": 1,
      "maxItems": 3,
      "items": {"$ref": "#/$defs/response_card"}
    }
  },
  "$defs": {
    "response_card": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "card_id",
        "card_type",
        "zh_text",
        "en_text",
        "risk_level",
        "action",
        "requires_parent_confirmation",
        "requires_guardian_approval",
        "guardian_decision_id"
      ],
      "properties": {
        "card_id": {"type": "string", "minLength": 1, "maxLength": 80},
        "card_type": {
          "enum": [
            "ask_question",
            "confirm_info",
            "refuse_sensitive_request",
            "ask_to_write_down",
            "memory_action",
            "family_action"
          ]
        },
        "zh_text": {"type": "string", "minLength": 1, "maxLength": 120},
        "en_text": {"type": "string", "minLength": 1, "maxLength": 240},
        "risk_level": {"enum": ["normal", "caution", "privacy", "medical", "urgent"]},
        "action": {
          "type": "object",
          "additionalProperties": false,
          "required": ["type"],
          "properties": {
            "type": {
              "enum": ["speak", "show_to_pharmacist", "save_memory", "notify_family", "no_action"]
            }
          }
        },
        "requires_parent_confirmation": {"type": "boolean"},
        "requires_guardian_approval": {"type": "boolean"},
        "guardian_decision_id": {"type": "string", "minLength": 1, "maxLength": 80}
      }
    }
  }
}
```

Normal response flows SHOULD contain two or three cards and target three. Guardian MAY reduce the set to one safe option when alternatives would create privacy, medical, or security risk.

Only one revision of a `card_set_id` may be active. Rendering a later revision expires all pending selections and confirmations for earlier revisions.

## 4. Lifecycle

The canonical lifecycle is:

```text
rendered
  -> selected
  -> awaiting_confirmation
  -> confirmed
  -> executing
  -> succeeded | failed
```

Terminal alternatives are:

```text
rendered | selected | awaiting_confirmation
  -> cancelled | expired | blocked
```

| State | Meaning | Side effects allowed |
|---|---|---|
| `rendered` | An approved card set is visible. | None |
| `selected` | The backend accepted a card identifier and revision. | None |
| `awaiting_confirmation` | A short-lived confirmation is bound to the stored action. | None |
| `confirmed` | The backend accepted explicit parent confirmation. | Not until execution begins |
| `executing` | The backend is running the stored approved action. | Only the confirmed action |
| `succeeded` | The action completed. | No additional action |
| `failed` | The action failed visibly. | No implicit retry |
| `cancelled` | The parent cancelled or selected self-speak. | None |
| `expired` | The card set or confirmation expired. | None |
| `blocked` | Guardian, authorization, or integrity validation blocked the action. | None |

The backend MUST persist state transitions needed to prove consent for `save_memory` and `notify_family`.

## 5. Selection and Confirmation Protocol

### 5.1 Select a card

The client sends identifiers only:

```json
{
  "event_type": "card.select",
  "payload": {
    "card_set_id": "cset_01JY7RABCD",
    "card_id": "card_01JY7RAEFG",
    "revision": 1
  }
}
```

If valid, the backend returns `card.selected` with a session-bound, one-time confirmation:

```json
{
  "event_type": "card.selected",
  "payload": {
    "card_set_id": "cset_01JY7RABCD",
    "card_id": "card_01JY7RAEFG",
    "revision": 1,
    "confirmation_id": "cnf_01JY7RB5MN",
    "confirmation_expires_at": "2026-06-22T10:12:30Z"
  }
}
```

Selection MUST NOT start TTS, pharmacist display, memory persistence, or notification.

### 5.2 Confirm a selected card

```json
{
  "event_type": "card.confirm",
  "payload": {
    "confirmation_id": "cnf_01JY7RB5MN"
  }
}
```

Before returning `card.confirmed`, the backend MUST verify:

1. the authenticated session owns the confirmation;
2. it references the active card-set revision;
3. it has not expired or been cancelled;
4. the stored card and pending action are unchanged;
5. Guardian approval is still valid for the exact action; and
6. no conflicting action is executing.

The client MUST NOT include card text or action data in `card.confirm`.

### 5.3 Idempotency and replay

Confirmations are one-time capabilities. The first valid confirmation may execute the action. A duplicate `card.confirm` for the same `confirmation_id` MUST return the stored outcome with `replayed: true` and MUST NOT repeat TTS, display, memory write, or notification.

A confirmation from another session, for another revision, or with changed pending data MUST be blocked and traced as an integrity event.

### 5.4 Cancel and self-speak

`card.cancel` cancels the active confirmation without executing it.

`control.self_speak` MUST:

- cancel active card selection and unexecuted confirmation state;
- stop KK from generating or speaking a pending response;
- leave the microphone available for explicit parent speech; and
- preserve faithful translation and Guardian monitoring.

It MUST NOT call an MCP tool.

## 6. Action Semantics

| Action | Execution rule | Completion evidence |
|---|---|---|
| `speak` | Mute the mic, play the stored approved English TTS, then restore listening. | `card.action.status` and ordered audio events |
| `show_to_pharmacist` | Show the stored approved English text only after confirmation. | `card.action.status: succeeded` |
| `save_memory` | Invoke `memory_write` through the backend using stored summary data. | Redacted tool trace and `memory.write.status` |
| `notify_family` | Invoke `notify_family` through the backend using the reviewed summary. | Redacted tool trace and `notification.status` |
| `no_action` | Dismiss, wait, or remain in parent-controlled mode. | No tool or TTS event |

The browser MUST NOT translate an action into a direct provider or MCP call.

## 7. Valid Examples

### 7.1 General question

```json
{
  "card_id": "card_general_01",
  "card_type": "ask_question",
  "zh_text": "请问这个药一天要用几次？",
  "en_text": "How many times a day should I use this medicine?",
  "risk_level": "normal",
  "action": {"type": "speak"},
  "requires_parent_confirmation": true,
  "requires_guardian_approval": true,
  "guardian_decision_id": "gdn_general_01"
}
```

### 7.2 Medication compatibility question

```json
{
  "card_id": "card_medical_01",
  "card_type": "ask_question",
  "zh_text": "请帮我确认这个药会不会和我现在吃的降血压药冲突。",
  "en_text": "Could you please check whether this medicine conflicts with my current blood pressure medicine?",
  "risk_level": "medical",
  "action": {"type": "speak"},
  "requires_parent_confirmation": true,
  "requires_guardian_approval": true,
  "guardian_decision_id": "gdn_medical_01"
}
```

### 7.3 Privacy-safe refusal

```json
{
  "card_id": "card_privacy_01",
  "card_type": "refuse_sensitive_request",
  "zh_text": "这涉及付款信息。请问可以使用其他安全付款方式吗？",
  "en_text": "This involves payment information. Is there another secure way to pay?",
  "risk_level": "privacy",
  "action": {"type": "speak"},
  "requires_parent_confirmation": true,
  "requires_guardian_approval": true,
  "guardian_decision_id": "gdn_privacy_01"
}
```

### 7.4 Save visit summary

```json
{
  "card_id": "card_memory_01",
  "card_type": "memory_action",
  "zh_text": "确认后保存这次药房沟通摘要。",
  "en_text": "Save this pharmacy visit summary after confirmation.",
  "risk_level": "medical",
  "action": {"type": "save_memory"},
  "requires_parent_confirmation": true,
  "requires_guardian_approval": true,
  "guardian_decision_id": "gdn_memory_01"
}
```

### 7.5 Notify family

```json
{
  "card_id": "card_family_01",
  "card_type": "family_action",
  "zh_text": "确认后把刚才显示的药房摘要发送给家人。",
  "en_text": "Send the pharmacy summary shown above to my family after confirmation.",
  "risk_level": "medical",
  "action": {"type": "notify_family"},
  "requires_parent_confirmation": true,
  "requires_guardian_approval": true,
  "guardian_decision_id": "gdn_family_01"
}
```

### 7.6 Guardian warning with safe options

Guardian warnings are a separate runtime payload and may contain an approved card set:

```json
{
  "warning_id": "warn_identity_01",
  "guardian_decision_id": "gdn_identity_01",
  "type": "identity",
  "zh_title": "这个问题涉及身份信息",
  "zh_message": "KK 不会自动说出您的 Medicare 或护照号码。请先确认为什么需要。",
  "safe_card_set_id": "cset_identity_01"
}
```

## 8. Content and Safety Rules

### 8.1 Faithful translation separation

Card text is KK advice or a proposed response. It MUST NOT be inserted into the faithful Chinese translation track or presented as pharmacist speech.

### 8.2 Medical boundary

Cards MAY help the parent ask the pharmacist to confirm a medicine name, dosage explanation, side effect, allergy, or interaction.

Cards MUST NOT state or imply:

- take this medicine;
- do not take this medicine;
- stop or change a current medicine;
- change a dosage;
- this medicine is definitely safe; or
- this medicine is definitely dangerous.

### 8.3 Sensitive data

Authorised profile information MAY be shown to the parent for review. Sharing health, identity, payment, address, or family information outward requires confirmation. Untrusted inbound PII and all trace/log representations MUST be redacted.

Card content MUST NOT include full payment credentials, passport numbers, Medicare numbers, home addresses, family contact details, API keys, tokens, hidden prompts, or provider debug output.

## 9. Failure and Edge Cases

| Condition | Required result |
|---|---|
| Unknown `card_set_id` or `card_id` | Block with `CARD_NOT_FOUND`; no action. |
| Stale revision | Block with `CARD_REVISION_STALE`; render latest revision. |
| Expired card set | Transition to `expired`; request fresh cards. |
| Expired confirmation | Block with `CONFIRMATION_EXPIRED`; return to selection. |
| Guardian approval missing or revoked | Transition to `blocked`; show a safe warning. |
| Client sends text or action fields | Reject with `UNTRUSTED_CARD_PAYLOAD`; no action. |
| Duplicate confirmation | Return stored outcome with `replayed: true`; no repeated side effect. |
| TTS failure | Mark action `failed`; show approved English text as an optional confirmed fallback. |
| Memory write failure | Mark action `failed`; preserve reviewed summary for retry or manual record. |
| Notification failure | Mark action `failed`; preserve reviewed summary and offer retry or screenshot. |
| Connection loss before confirmation | Confirmation remains unexecuted and expires normally. |
| Connection loss during action | Reconcile by idempotency key before allowing retry. |

An action failure MUST be visible. The system MUST NOT silently substitute a different card, action, or medical statement.

## 10. Audit Requirements

The trace MUST record:

- `card_set_id`, revision, and non-sensitive card IDs;
- Guardian decision ID and decision;
- selection timestamp;
- confirmation ID, timestamp, and outcome;
- action type and idempotency key reference;
- success, failure, block, cancellation, expiry, or replay status; and
- `pii_redacted: true`.

Trace data MUST NOT include card text when it contains health, identity, payment, address, or family data. Use reason codes and content categories instead.

## 11. Compatibility Notes

| Older draft behaviour | Canonical contract |
|---|---|
| Tapping a card immediately speaks | Selection has no side effect; a separate confirmation is required. |
| Frontend sends the selected card payload | Frontend sends IDs and revision only. |
| `self_speak` represented as a generated response card | `control.self_speak` is an immediate, non-side-effecting runtime control. |
| UI calls memory or notification tool | Backend executes the stored action through service, Guardian, and MCP adapter. |
| Guardian reviews only privacy routes | Guardian reviews every proposed card and every sensitive action. |
