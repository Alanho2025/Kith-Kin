from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.fixtures.clock import MutableClock
from tests.fixtures.signing import TEST_SIGNING_KEY

TEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000002")
ORIGIN = "http://localhost:5173"


@pytest.fixture
def clock() -> MutableClock:
    return MutableClock()


@pytest.fixture
def app_client(clock: MutableClock) -> Iterator[TestClient]:
    settings = Settings(
        environment="test",
        cors_allowed_origins=[ORIGIN],
        app_ws_token_secret=TEST_SIGNING_KEY,
        app_ws_cookie_secure=False,
        live_transport="backend_proxy",
    )
    with TestClient(create_app(settings=settings, user_id=TEST_USER_ID, clock=clock.now)) as client:
        yield client


def create_session(client: TestClient) -> str:
    response = client.post("/api/sessions", json={"encounter_type": "pharmacy"})
    assert response.status_code == 201
    return str(response.json()["session_id"])


def issue_ticket(client: TestClient, session_id: str, *, origin: str = ORIGIN) -> str:
    response = client.post(
        f"/api/sessions/{session_id}/ticket",
        headers={"origin": origin},
    )
    assert response.status_code == 201
    ticket = client.cookies.get("kk_live_ticket")
    assert ticket
    return ticket
