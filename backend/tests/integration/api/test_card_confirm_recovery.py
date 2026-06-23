from fastapi.testclient import TestClient

from .conftest import ORIGIN, create_session, issue_ticket


def test_runtime_rejects_arbitrary_confirm_but_http_recovery_remains_legacy(
    app_client: TestClient,
) -> None:
    session_id = create_session(app_client)
    issue_ticket(app_client, session_id)
    confirmation_id = "confirmation-shared-1"

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
        blocked = socket.receive_json()
        assert blocked["event_type"] == "card.action.status"
        assert blocked["payload"] == {
            "confirmation_id": confirmation_id,
            "action_type": "no_action",
            "phase": "blocked",
            "code": "CARD_NOT_FOUND",
        }

    recovered = app_client.post(
        "/api/cards/confirm",
        json={"confirmation_id": confirmation_id},
    )
    assert recovered.status_code == 200
    assert recovered.json() == {
        "confirmation_id": confirmation_id,
        "status": "confirmed",
        "replayed": False,
    }

    replayed = app_client.post(
        "/api/cards/confirm",
        json={"confirmation_id": confirmation_id},
    )
    assert replayed.status_code == 200
    assert replayed.json() == {
        "confirmation_id": confirmation_id,
        "status": "confirmed",
        "replayed": True,
    }
