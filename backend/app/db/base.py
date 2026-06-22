"""SQLAlchemy declarative base and model metadata imports."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLite-backed ORM models."""


def import_models() -> None:
    """Import models so Alembic and create_all see every table."""
    from app.db.models import (  # noqa: F401
        allergy,
        confirmation,
        medication,
        notification,
        session,
        ticket_use,
        trace_event,
        user,
        visit_summary,
    )
