import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command

ROOT = Path(__file__).resolve().parents[4]


def test_upgrade_downgrade_upgrade(tmp_path) -> None:
    database_path = tmp_path / "migration.db"
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{database_path}")

    command.upgrade(config, "head")
    assert _tables(database_path) >= {"users", "sessions", "ticket_uses", "trace_events"}

    command.downgrade(config, "base")
    assert "users" not in _tables(database_path)

    command.upgrade(config, "head")
    assert "visit_summaries" in _tables(database_path)


def _tables(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute("select name from sqlite_master where type='table'").fetchall()
    return {row[0] for row in rows}
