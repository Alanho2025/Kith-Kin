from datetime import datetime, timedelta
from uuid import UUID, uuid4

import jwt

TEST_SIGNING_KEY = "phase-04-test-signing-key-that-is-long-enough"
TEST_ISSUER = "kithkin-backend"
TEST_AUDIENCE = "kithkin-live-ws"


def make_ticket(
    *,
    session_id: UUID,
    user_id: UUID,
    origin: str,
    now: datetime,
    key: str = TEST_SIGNING_KEY,
    audience: str = TEST_AUDIENCE,
    purpose: str = "live_websocket",
    max_uses: int = 1,
    expires_in_seconds: int = 60,
) -> str:
    return jwt.encode(
        {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "jti": str(uuid4()),
            "purpose": purpose,
            "iss": TEST_ISSUER,
            "aud": audience,
            "origin": origin,
            "iat": now,
            "exp": now + timedelta(seconds=expires_in_seconds),
            "max_uses": max_uses,
        },
        key,
        algorithm="HS256",
    )
