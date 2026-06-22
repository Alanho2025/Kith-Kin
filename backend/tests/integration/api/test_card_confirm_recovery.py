from fastapi.testclient import TestClient

from .conftest import ORIGIN, create_session, issue_ticket


def test_http_and_ws_share_idempotent_service(app_client: TestClient) -> None:
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
        confirmed = socket.receive_json()
        assert confirmed["event_type"] == "card.confirmed"
        assert confirmed["payload"]["replayed"] is False

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
