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
        "*.db",
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


def test_backend_production_code_does_not_branch_on_eval_case_ids() -> None:
    offenders: list[str] = []
    for path in (ROOT / "backend/app").rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if "eval-015" in content:
            offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_runtime_contract_documents_product_options_event() -> None:
    content = (ROOT / "specs/runtime-event-contract.md").read_text(encoding="utf-8")

    assert "| `product.options.render` |" in content
    assert "pharmacist_stated_use" in content
    assert "pharmacist_stated_directions" in content
    assert "pharmacist_stated_cautions" in content
    assert "MUST NOT contain AI-generated pros, cons, ranking, suitability" in content
