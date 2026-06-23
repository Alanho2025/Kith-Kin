import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from .conftest import ORIGIN, create_session, issue_ticket


def test_replays_only_sequence_after_last_seen(app_client: TestClient) -> None:
    session_id = create_session(app_client)
    issue_ticket(app_client, session_id)
    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as first:
        assert first.receive_json()["sequence"] == 1
        assert first.receive_json()["sequence"] == 2

    issue_ticket(app_client, session_id)
    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live?last_seen_sequence=1",
        headers={"origin": ORIGIN},
    ) as resumed:
        replay = resumed.receive_json()
        assert replay["sequence"] == 2
        assert replay["event_type"] == "audio.listening"


def test_stale_sequence_emits_resume_unavailable_then_closes(
    app_client: TestClient,
) -> None:
    session_id = create_session(app_client)
    issue_ticket(app_client, session_id)
    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as first:
        first.receive_json()
        first.receive_json()
        for index in range(70):
            first.send_json(
                {
                    "schema_version": "0.1",
                    "event_id": f"cmd-{index}",
                    "event_type": "control.self_speak",
                    "session_id": session_id,
                    "sequence": index + 1,
                    "timestamp": "2026-06-22T00:00:00Z",
                    "correlation_id": None,
                    "payload": {},
                }
            )
            first.receive_json()

    issue_ticket(app_client, session_id)
    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live?last_seen_sequence=0",
        headers={"origin": ORIGIN},
    ) as stale:
        fallback = stale.receive_json()
        assert fallback["event_type"] == "fallback.show"
        assert fallback["payload"]["code"] == "SESSION_RESUME_UNAVAILABLE"
        with pytest.raises(WebSocketDisconnect):
            stale.receive_json()
