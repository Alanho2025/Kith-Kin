import importlib.util
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[4]


async def test_seed_and_cleanup_are_idempotent(tmp_path) -> None:
    seed = _load_seed()
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}"

    first = await seed(database_url, cleanup=False)
    second = await seed(database_url, cleanup=False)
    cleanup = await seed(database_url, cleanup=True)

    assert first == second == {"users": 1, "medications": 1, "allergies": 1, "visit_summaries": 1}
    assert cleanup == {"users": 0, "medications": 0, "allergies": 0, "visit_summaries": 0}


def _load_seed() -> Any:
    spec = importlib.util.spec_from_file_location(
        "seed_demo_data",
        ROOT / "scripts/seed_demo_data.py",
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return cast(Any, module.seed)
