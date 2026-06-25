"""Async SQLite engine and session factory helpers."""

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.db.base import Base, import_models

AsyncSessionFactory = async_sessionmaker[AsyncSession]


def create_engine(database_url: str) -> AsyncEngine:
    """Create the application async SQLAlchemy engine."""
    connect_args: dict[str, object] = {}
    if database_url.startswith("sqlite"):
        connect_args = {"timeout": 30.0, "check_same_thread": False}
    engine = create_async_engine(database_url, future=True, connect_args=connect_args)
    if database_url.startswith("sqlite"):
        @event.listens_for(engine.sync_engine, "connect")
        def _configure_sqlite(dbapi_connection: Any, _connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()
    return engine


def create_session_factory(engine: AsyncEngine) -> AsyncSessionFactory:
    """Create a typed async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False)


async def initialize_database(engine: AsyncEngine) -> None:
    """Create tables for test harnesses that do not run Alembic."""
    import_models()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def session_scope(factory: AsyncSessionFactory) -> AsyncIterator[AsyncSession]:
    """Yield one transaction-owned async session."""
    async with factory() as session:
        async with session.begin():
            yield session
