"""Environment-backed application configuration with fail-closed validation."""

from datetime import timedelta
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Kith&Kin settings loaded only at the application composition root."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    deployment_mode: str = "local"
    live_transport: Literal["backend_proxy", "gemini_live"] = "backend_proxy"
    session_store: Literal["sqlite"] = "sqlite"
    mcp_transport: Literal["stdio"] = "stdio"
    notification_provider: Literal["stub"] = "stub"

    database_url: str = "sqlite+aiosqlite:///kithkin.db"
    test_database_url: str = "sqlite+aiosqlite:///kithkin_test.db"

    google_api_key: SecretStr = SecretStr("")
    google_genai_use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "global"
    gemini_api_version: str = "v1alpha"
    gemini_live_model: str = "gemini-3.1-flash-live-preview"
    gemini_text_model: str = "gemini-2.5-flash"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    gemini_tts_voice_name: str = "charon"
    gemini_live_translate_model: str = "gemini-3.5-live-translate-preview"
    live_translation_fallback_enabled: bool = False

    app_ws_token_secret: SecretStr = SecretStr("")
    app_ws_token_ttl_seconds: int = 60
    app_ws_token_issuer: str = "kithkin-backend"
    app_ws_token_audience: str = "kithkin-live-ws"
    app_ws_token_max_uses: int = 1
    app_ws_cookie_name: str = "kk_live_ticket"
    app_ws_cookie_samesite: Literal["strict"] = "strict"
    app_ws_cookie_secure: bool = False

    live_session_max_seconds: int = 840
    rag_max_records: int = 5
    rag_max_context_chars: int = 4000
    rag_timeout_ms: int = 1500
    translation_timeout_ms: int = 4000
    drug_check_timeout_ms: int = 2500
    memory_write_timeout_ms: int = 3000
    notification_timeout_ms: int = 5000
    trace_retention_days: int = 30
    visit_retention_days: int = 30

    @model_validator(mode="after")
    def validate_security_invariants(self) -> "Settings":
        """Reject unsafe production credentials and invalid runtime bounds."""
        if not 1 <= self.app_ws_token_ttl_seconds <= 300:
            raise ValueError("CONFIG_TOKEN_TTL_INVALID")
        if min(self.rag_max_records, self.rag_max_context_chars, self.rag_timeout_ms) <= 0:
            raise ValueError("CONFIG_RAG_LIMIT_INVALID")
        if not self.cors_allowed_origins:
            raise ValueError("CONFIG_ORIGIN_REQUIRED")
        if self.environment == "production":
            if not self.app_ws_token_secret.get_secret_value():
                raise ValueError("CONFIG_SECRET_REQUIRED")
            if not self.app_ws_cookie_secure:
                raise ValueError("CONFIG_INSECURE_COOKIE")
        return self

    @property
    def app_ws_token_ttl_seconds_delta(self) -> timedelta:
        return timedelta(seconds=self.app_ws_token_ttl_seconds)
