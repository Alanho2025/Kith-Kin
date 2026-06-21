# Phase 09: Visit Memory, Notification, and Recall Implementation Plan

## Goal

Complete the two-visit hero flow with confirmed summary writes, a deterministic notification stub, and safe cross-session recall.

## Non-Goals

No real SMS/email, automatic family disclosure, or clinical record integration.

## Source of Truth

MCP/card specs and hero-flow requirements.

## Previous Phase Artifacts

Confirmed action executor, repositories, RAG, Guardian, cards.

## Entry Conditions

Phase 08 green.

## Exit Checkpoint

Two-visit integration and browser hero flow pass with complete consent/tool traces.

## Files

Create visit-summary service, notification gateway/stub, demo inbox DTO, hero integration tests and two-session fixtures. Modify session-end and session-start services.

## Public Contracts

Summary shape follows MCP spec. `NotificationGateway.send` accepts backend-resolved destination and approved summary; frontend never supplies destination.

## Data Flows

End visit→summary proposal→Guardian→review→confirmation→memory write/optional notification. Next visit→bounded prefetch→safe reminder card. Failures preserve reviewed summary and never report false success.

## TDD Tasks

1. Summary review before write.
2. Confirmed idempotent memory write.
3. Confirmed stub notification and retry failure.
4. Second-session bounded recall.
5. Recall generates a question, not advice.
6. Hero browser sequence.

## Stop Conditions

Unconfirmed write/send, caller destination, invented history, or medical conclusion blocks Phase 10.

## Commit Boundaries

- `feat(memory): add confirmed visit summaries`
- `feat(notification): add auditable local stub`
- `feat(memory): recall prior pharmacy questions`

## Next Artifacts

Hero workflow, notification record, cross-session recall and trace evidence.

## Exact File Manifest

- Create `backend/app/services/visit_summary_service.py`, `visit_completion_service.py`, `notification_service.py`.
- Create `backend/app/adapters/notification_adapter.py` with `LocalNotificationStub`; no network provider.
- Create `backend/app/repositories/notification_repository.py` and schemas `backend/app/schemas/visit_summary.py`, `notification.py`.
- Create `backend/tests/integration/hero/test_two_visit_flow.py`, `test_memory_write_confirmation.py`, `test_notification_confirmation.py`.
- Create fixtures `backend/tests/fixtures/hero/first_visit.py`, `second_visit.py`, `local_family_destination.py`.
- Modify session start prefetch and session end orchestration; modify frontend summary page to render existing events only.
- Migration: `0003_notification_outcomes.py` only if the Phase 05 notification table lacks idempotent outcome fields. Seed adds one synthetic authorised family destination; no real address or number.

## Public Signatures and Errors

```python
class NotificationGateway(Protocol):
    async def send(
        self, destination: AuthorisedFamilyDestination,
        summary: ApprovedVisitSummary,
        *, idempotency_key: UUID,
    ) -> NotificationOutcome: ...

class VisitCompletionService:
    async def prepare_summary(
        self, session_id: UUID, context: TrustedRequestContext
    ) -> SummaryReview: ...
    async def execute_confirmed_action(
        self, confirmation: ConsumedConfirmation, context: TrustedRequestContext
    ) -> ConfirmedVisitActionOutcome: ...
```

Errors are `SUMMARY_UNAVAILABLE`, `SUMMARY_NOT_APPROVED`, `MEMORY_WRITE_BLOCKED`, `MEMORY_UNAVAILABLE`, `NOTIFICATION_DESTINATION_UNAVAILABLE`, `NOTIFICATION_UNAVAILABLE`, and `IDEMPOTENCY_CONFLICT`. The browser never supplies `user_id`, destination, recipient, tool input, or urgency.

## Exact Flow Rules

- `summary.render` occurs before any save/send confirmation and contains reviewed structured fields only.
- Guardian approval and the exact summary hash are bound to separate save/notify cards.
- Confirmed save calls `memory_write` once; confirmed notify resolves destination server-side and calls the stub once.
- Failures retain the on-screen reviewed summary and emit failed status; no false success or automatic alternate destination.
- The next session prefetches bounded medication/allergy/visit snippets. Prior visit content supports a pharmacist question, never a conclusion.

## Executable TDD Ledger

| Cycle | RED | Named assertion | GREEN |
|---|---|---|---|
| 09.1 | `test_memory_write_confirmation.py::test_summary_render_precedes_write` | write count before confirm is zero | summary review workflow |
| 09.2 | `test_memory_write_confirmation.py::test_confirmed_write_is_idempotent` | one row and replay true | confirmed executor/repository |
| 09.3 | `test_notification_confirmation.py::test_destination_is_backend_resolved` | caller destination accepted | notification service |
| 09.4 | `test_notification_confirmation.py::test_stub_failure_is_visible_and_not_retried_with_new_key` | duplicate/send success | stored failed outcome |
| 09.5 | `test_two_visit_flow.py::test_second_visit_recalls_authorised_summary` | missing prior snippet | session prefetch |
| 09.6 | `test_two_visit_flow.py::test_recall_card_is_question_not_medical_advice` | forbidden phrase/tool path | Companion/Guardian flow |

Complete cross-session RED:

```python
@pytest.mark.asyncio
async def test_second_visit_recalls_authorised_summary(hero, parent_context):
    first = await hero.complete_first_visit(parent_context, confirm_save=True)
    second = await hero.start_second_visit(parent_context.user_id)
    assert first.memory_write.replayed is False
    assert any(item.record_type == "visit_summary" for item in second.prefetched.snippets)
    assert second.proposed_card.action.type == CardActionType.SPEAK
    assert second.proposed_card.requires_parent_confirmation is True
```

Verify focused RED/GREEN, then EVAL-007, EVAL-008, and EVAL-015 plus full regression. Refactor may share idempotent outcome code but may not combine save and notify confirmation IDs. Migration round-trip and seed cleanup are required. Any unconfirmed write/send or caller-controlled destination blocks Phase 10.
