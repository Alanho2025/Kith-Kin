from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_required_environment_examples_exist() -> None:
    required = [
        ROOT / ".env.example",
        ROOT / "backend/.env.example",
        ROOT / "frontend/.env.example",
    ]

    assert [path for path in required if not path.exists()] == []


def test_gitignore_covers_sensitive_and_generated_artifacts() -> None:
    content = (ROOT / ".gitignore").read_text(encoding="utf-8")
    required_patterns = {
        ".env",
        "!.env.example",
        "!**/.env.example",
        ".postgres-data/",
        "evals/traces/",
        "output/",
        ".coverage",
        "frontend/dist/",
        "node_modules/",
        ".venv/",
        "*.tsbuildinfo",
    }

    assert required_patterns <= set(content.splitlines())


def test_frontend_environment_contains_no_privileged_configuration() -> None:
    content = (ROOT / "frontend/.env.example").read_text(encoding="utf-8")
    forbidden = ("GEMINI", "GOOGLE_API_KEY", "DATABASE_URL", "MCP", "TOKEN_SECRET")

    assert [name for name in forbidden if name in content] == []
