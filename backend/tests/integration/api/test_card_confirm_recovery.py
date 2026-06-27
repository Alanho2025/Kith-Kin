from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.core.constants import CardActionType
from app.domain.confirmation import StoredConfirmation

from .conftest import ORIGIN, create_session, issue_ticket


def test_runtime_rejects_arbitrary_confirm_but_http_recovery_remains_legacy(
    app_client: TestClient,
) -> None:
    session_id = create_session(app_client)
    issue_ticket(app_client, session_id)
    confirmation_id = "confirmation-shared-1"

    from app.domain.credentials import TrustedRequestContext
    from app.services.card_service import _action_hash
    from tests.fixtures.clock import MutableClock
    from tests.unit.services.test_card_service import approved_card_set

    context = TrustedRequestContext(
        session_id=UUID(session_id), user_id=app_client.app.state.user_id, origin="test"
    )
    card_set = approved_card_set(MutableClock())
    app_client.app.state.card_service.register_card_set(card_set, context)

    app_client.app.state.card_service._repository.add(
        StoredConfirmation(
            confirmation_id=confirmation_id,
            session_id=UUID(session_id),
            user_id=app_client.app.state.user_id,
            card_set_id=card_set.card_set_id,
            card_id=card_set.cards[0].card_id,
            revision=1,
            action_type=CardActionType.SPEAK,
            action_hash=_action_hash(card_set.cards[0]),
            guardian_decision_id="g1",
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            idempotency_key=uuid4(),
            state="selected",
        )
    )

    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        socket.receive_json()
        socket.receive_json()
        socket.send_json(
            {
                "schema_version": "0.1",
                "event_id": "cmd-confirm-1",
                "event_type": "card.confirm",
                "session_id": session_id,
                "sequence": 1,
                "timestamp": "2026-06-22T00:00:00Z",
                "correlation_id": None,
                "payload": {"confirmation_id": confirmation_id},
            }
        )
        confirmed = socket.receive_json()
        assert confirmed["event_type"] == "card.confirmed"
        assert confirmed["payload"] == {
            "confirmation_id": confirmation_id,
            "action_type": "show_to_pharmacist",
            "replayed": False,
        }

    recovered = app_client.post(
        "/api/cards/confirm",
        json={"confirmation_id": confirmation_id},
    )
    assert recovered.status_code == 200
    assert recovered.json() == {
        "confirmation_id": confirmation_id,
        "status": "confirmed",
        "replayed": True,
    }
