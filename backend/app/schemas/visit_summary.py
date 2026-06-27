"""Pydantic schemas for visit summary reviews."""

from app.schemas.mcp import VisitSummaryValue


class SummaryReview(VisitSummaryValue):
    """A user-reviewed draft summary of the medical encounter."""
    pass
