import pytest
from pydantic import ValidationError

from app.core.config import Settings


def base_environment() -> dict[str, object]:
    return {
        "environment": "development",
        "google_api_key": "",
        "app_ws_token_secret": "",
        "app_ws_cookie_secure": False,
    }


def test_accepts_safe_development_configuration() -> None:
    settings = Settings(**base_environment())

    assert settings.app_ws_token_ttl_seconds == 60
    assert settings.rag_max_records == 5
    assert settings.rag_max_context_chars == 4000


def test_production_requires_ticket_secret() -> None:
    values = base_environment() | {"environment": "production"}

    with pytest.raises(ValidationError, match="CONFIG_SECRET_REQUIRED"):
        Settings(**values)


def test_production_requires_secure_cookie() -> None:
    values = base_environment() | {
        "environment": "production",
        "app_ws_token_secret": "a" * 32,
    }

    with pytest.raises(ValidationError, match="CONFIG_INSECURE_COOKIE"):
        Settings(**values)


@pytest.mark.parametrize("ttl", [0, 301])
def test_rejects_ticket_ttl_outside_allowed_range(ttl: int) -> None:
    with pytest.raises(ValidationError, match="CONFIG_TOKEN_TTL_INVALID"):
        Settings(**(base_environment() | {"app_ws_token_ttl_seconds": ttl}))


@pytest.mark.parametrize(
    ("field", "value"),
    [("rag_max_records", 0), ("rag_max_context_chars", 0), ("rag_timeout_ms", 0)],
)
def test_rejects_non_positive_rag_limits(field: str, value: int) -> None:
    with pytest.raises(ValidationError, match="CONFIG_RAG_LIMIT_INVALID"):
        Settings(**(base_environment() | {field: value}))
