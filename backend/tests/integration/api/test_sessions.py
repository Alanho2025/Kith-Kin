from fastapi.testclient import TestClient

from .conftest import ORIGIN, create_session


def test_ticket_cookie_is_http_only_strict_and_session_bound(app_client: TestClient) -> None:
    session_id = create_session(app_client)

    response = app_client.post(
        f"/api/sessions/{session_id}/ticket",
        headers={"origin": ORIGIN},
    )

    assert response.status_code == 201
    assert response.json() == {
        "session_id": session_id,
        "expires_at": "2026-06-22T00:01:00Z",
        "max_uses": 1,
    }
    assert "encoded_ticket" not in response.text
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert f"Path=/api/sessions/{session_id}/live" in cookie


def test_end_session_blocks_new_ticket(app_client: TestClient) -> None:
    session_id = create_session(app_client)
    ended = app_client.post(
        f"/api/sessions/{session_id}/end",
        json={"reason": "user_completed"},
    )

    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    ticket = app_client.post(
        f"/api/sessions/{session_id}/ticket",
        headers={"origin": ORIGIN},
    )
    assert ticket.status_code == 409
    assert ticket.json()["code"] == "SESSION_NOT_CONNECTABLE"
