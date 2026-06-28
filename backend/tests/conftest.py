import pytest


@pytest.fixture(autouse=True)
def mock_no_google_api_key(monkeypatch, request) -> None:
    """Strip API keys to prevent tests from hitting real endpoints.

    Explicit live tests opt out.
    """
    if "test_adk_live" in request.node.nodeid:
        return
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
