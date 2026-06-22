"""User profile repository."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from app.db.models.user import User
from app.db.session import AsyncSessionFactory


@dataclass(frozen=True)
class UserProfile:
    """Safe user profile projection."""

    user_id: UUID
    display_name: str
    preferred_language: str
    family_contact_label: str | None


class UserRepository:
    """Persist and retrieve authorised parent profiles."""

    def __init__(
        self,
        session_factory: AsyncSessionFactory,
        clock: Callable[[], datetime],
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def ensure_demo_user(
        self,
        user_id: UUID,
        *,
        display_name: str = "Demo parent",
        family_contact_label: str | None = "Adult child",
    ) -> None:
        async with self._session_factory() as session:
            existing = await session.get(User, user_id)
            now = self._clock()
            if existing is None:
                session.add(
                    User(
                        id=user_id,
                        display_name=display_name,
                        preferred_language="zh_cn",
                        family_contact_label=family_contact_label,
                        created_at=now,
                        updated_at=now,
                    )
                )
            else:
                existing.display_name = display_name
                existing.family_contact_label = family_contact_label
                existing.updated_at = now
            await session.commit()

    async def get(self, user_id: UUID) -> UserProfile | None:
        async with self._session_factory() as session:
            row = await session.scalar(select(User).where(User.id == user_id))
            if row is None:
                return None
            return UserProfile(
                user_id=row.id,
                display_name=row.display_name,
                preferred_language=row.preferred_language,
                family_contact_label=row.family_contact_label,
            )
