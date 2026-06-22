from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from tests.fixtures.clock import MutableClock
from tests.fixtures.signing import TEST_AUDIENCE, TEST_SIGNING_KEY, make_ticket

from .conftest import ORIGIN, OTHER_USER_ID, TEST_USER_ID, create_session, issue_ticket


def set_ticket(client: TestClient, ticket: str) -> None:
    client.cookies.set("kk_live_ticket", ticket)


def test_expired_ticket_closes_4401(
    app_client: TestClient,
    clock: MutableClock,
) -> None:
    session_id = create_session(app_client)
    issue_ticket(app_client, session_id)
    clock.advance(seconds=61)

    with pytest.raises(WebSocketDisconnect) as closed:
        with app_client.websocket_connect(
            f"/api/sessions/{session_id}/live",
            headers={"origin": ORIGIN},
        ):
            pass
    assert closed.value.code == 4401


@pytest.mark.parametrize(
    "case",
    ["wrong_origin", "wrong_audience", "wrong_purpose", "wrong_session", "wrong_user"],
)
def test_wrong_scope_closes_4403(
    app_client: TestClient,
    clock: MutableClock,
    case: str,
) -> None:
    session_id = create_session(app_client)
    other_session_id = create_session(app_client)
    claim_session_id = UUID(session_id)
    user_id = TEST_USER_ID
    origin = ORIGIN
    audience = TEST_AUDIENCE
    purpose = "live_websocket"
    connect_session_id = session_id
    connect_origin = ORIGIN
    if case == "wrong_origin":
        connect_origin = "http://evil.example"
    elif case == "wrong_audience":
        audience = "gemini-live"
    elif case == "wrong_purpose":
        purpose = "gemini_live"
    elif case == "wrong_session":
        connect_session_id = other_session_id
    elif case == "wrong_user":
        user_id = OTHER_USER_ID
    ticket = make_ticket(
        session_id=claim_session_id,
        user_id=user_id,
        origin=origin,
        now=clock.now(),
        audience=audience,
        purpose=purpose,
    )
    set_ticket(app_client, ticket)

    with pytest.raises(WebSocketDisconnect) as closed:
        with app_client.websocket_connect(
            f"/api/sessions/{connect_session_id}/live",
            headers={"origin": connect_origin},
        ):
            pass
    assert closed.value.code == 4403


def test_invalid_signature_closes_4401(
    app_client: TestClient,
    clock: MutableClock,
) -> None:
    session_id = create_session(app_client)
    ticket = make_ticket(
        session_id=UUID(session_id),
        user_id=TEST_USER_ID,
        origin=ORIGIN,
        now=clock.now(),
        key=f"{TEST_SIGNING_KEY}-wrong",
    )
    set_ticket(app_client, ticket)

    with pytest.raises(WebSocketDisconnect) as closed:
        with app_client.websocket_connect(
            f"/api/sessions/{session_id}/live",
            headers={"origin": ORIGIN},
        ):
            pass
    assert closed.value.code == 4401


def test_missing_ticket_closes_4401(app_client: TestClient) -> None:
    session_id = create_session(app_client)

    with pytest.raises(WebSocketDisconnect) as closed:
        with app_client.websocket_connect(
            f"/api/sessions/{session_id}/live",
            headers={"origin": ORIGIN},
        ):
            pass
    assert closed.value.code == 4401


def test_ended_session_closes_4410(app_client: TestClient) -> None:
    session_id = create_session(app_client)
    ticket = issue_ticket(app_client, session_id)
    ended = app_client.post(
        f"/api/sessions/{session_id}/end",
        json={"reason": "user_completed"},
    )
    assert ended.status_code == 200
    set_ticket(app_client, ticket)

    with pytest.raises(WebSocketDisconnect) as closed:
        with app_client.websocket_connect(
            f"/api/sessions/{session_id}/live",
            headers={"origin": ORIGIN},
        ):
            pass
    assert closed.value.code == 4410


def test_ticket_replay_closes_4409(app_client: TestClient) -> None:
    session_id = create_session(app_client)
    ticket = issue_ticket(app_client, session_id)
    with app_client.websocket_connect(
        f"/api/sessions/{session_id}/live",
        headers={"origin": ORIGIN},
    ) as socket:
        assert socket.receive_json()["event_type"] == "session.ready"

    set_ticket(app_client, ticket)
    with pytest.raises(WebSocketDisconnect) as replay:
        with app_client.websocket_connect(
            f"/api/sessions/{session_id}/live",
            headers={"origin": ORIGIN},
        ):
            pass
    assert replay.value.code == 4409
