"""Async SQLite engine and session factory helpers."""

from collections.abc import AsyncIterator

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
    return create_async_engine(database_url, future=True)


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
