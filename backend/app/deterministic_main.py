"""Deterministic backend entrypoint for CI Playwright smoke tests.

This keeps the browser test on the real FastAPI app, DB, ticket, WebSocket,
and runtime stack while preventing local or CI .env Gemini credentials from
turning merge-required smoke tests into provider integration tests.
"""

import os

from app.core.config import Settings
from app.main import create_app


settings = Settings(
    _env_file=None,
    environment="development",
    live_transport="backend_proxy",
    database_url=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///kithkin.db"),
    google_api_key="",
)

app = create_app(settings=settings)
