from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.db.models.user import User
from app.db.session import (
    AsyncSessionFactory,
    create_engine,
    create_session_factory,
    initialize_database,
)

TEST_USER_ID = UUID("00000000-0000-4000-8000-000000000001")
OTHER_USER_ID = UUID("00000000-0000-4000-8000-000000000002")
SESSION_ID = UUID("00000000-0000-4000-8000-000000000101")
NOW = datetime(2026, 6, 22, tzinfo=UTC)


@pytest.fixture
async def db_sessions(tmp_path) -> AsyncIterator[AsyncSessionFactory]:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'kithkin_test.db'}"
    engine = create_engine(database_url)
    await initialize_database(engine)
    factory = create_session_factory(engine)
    async with factory() as session:
        session.add_all(
            [
                User(
                    id=TEST_USER_ID,
                    display_name="Demo parent",
                    preferred_language="zh_cn",
                    family_contact_label="Adult child",
                    created_at=NOW,
                    updated_at=NOW,
                ),
                User(
                    id=OTHER_USER_ID,
                    display_name="Other parent",
                    preferred_language="zh_cn",
                    family_contact_label=None,
                    created_at=NOW,
                    updated_at=NOW,
                ),
            ]
        )
        await session.commit()
    yield factory
    await engine.dispose()
