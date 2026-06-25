import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command
from app.db.session import create_engine

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


async def test_sqlite_engine_uses_wal_and_busy_timeout(tmp_path) -> None:
    database_path = tmp_path / "engine.db"
    engine = create_engine(f"sqlite+aiosqlite:///{database_path}")
    async with engine.connect() as connection:
        journal_mode = await connection.exec_driver_sql("PRAGMA journal_mode")
        busy_timeout = await connection.exec_driver_sql("PRAGMA busy_timeout")
        assert journal_mode.scalar_one().lower() == "wal"
        assert busy_timeout.scalar_one() == 30000
    await engine.dispose()


def _tables(database_path: Path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        rows = connection.execute("select name from sqlite_master where type='table'").fetchall()
    return {row[0] for row in rows}
