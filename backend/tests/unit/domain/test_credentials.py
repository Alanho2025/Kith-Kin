from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.credentials import AppWebSocketTicketClaims

NOW = datetime(2026, 6, 22, tzinfo=UTC)


def valid_claims() -> dict[str, object]:
    return {
        "session_id": UUID(int=1),
        "user_id": UUID(int=2),
        "jti": UUID(int=3),
        "purpose": "live_websocket",
        "iss": "kithkin-backend",
        "aud": "kithkin-live-ws",
        "origin": "http://localhost:5173",
        "iat": NOW,
        "exp": NOW + timedelta(seconds=60),
        "max_uses": 1,
    }


def test_app_ticket_claims_are_single_use_and_session_bound() -> None:
    claims = AppWebSocketTicketClaims.model_validate(valid_claims())

    assert claims.max_uses == 1
    assert claims.session_id == UUID(int=1)


@pytest.mark.parametrize(
    ("field", "value"),
    [("purpose", "gemini_live"), ("max_uses", 2)],
)
def test_app_ticket_rejects_cross_purpose_or_multi_use(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        AppWebSocketTicketClaims.model_validate(valid_claims() | {field: value})


def test_app_ticket_expiry_must_follow_issue_time() -> None:
    with pytest.raises(ValidationError, match="TICKET_TIME_RANGE_INVALID"):
        AppWebSocketTicketClaims.model_validate(valid_claims() | {"exp": NOW})
