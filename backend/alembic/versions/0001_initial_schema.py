"""Initial SQLite schema for authorised memory, sessions, and traces."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("preferred_language", sa.String(length=20), nullable=False),
        sa.Column("family_contact_label", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("encounter_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sessions_user_status", "sessions", ["user_id", "status"])
    op.create_table(
        "medications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("dose", sa.String(length=120), nullable=True),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_medications_user_updated", "medications", ["user_id", "updated_at"])
    op.create_table(
        "allergies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("substance", sa.String(length=160), nullable=False),
        sa.Column("reaction", sa.String(length=500), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_allergies_user_updated", "allergies", ["user_id", "updated_at"])
    op.create_table(
        "visit_summaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_visit_summaries_idempotency_key"),
    )
    op.create_index("ix_visit_summaries_user_updated", "visit_summaries", ["user_id", "updated_at"])
    op.create_table(
        "ticket_uses",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("issuer", sa.String(length=120), nullable=False),
        sa.Column("jti", sa.Uuid(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("issuer", "jti", name="uq_ticket_uses_issuer_jti"),
    )
    op.create_table(
        "confirmations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("confirmation_id", sa.String(length=80), nullable=False),
        sa.Column("action_type", sa.String(length=40), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("session_id", "confirmation_id", name="uq_confirmations_session_id"),
    )
    op.create_index(
        "ix_confirmations_session_sequence",
        "confirmations",
        ["session_id", "sequence"],
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE")),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_notifications_idempotency_key"),
    )
    op.create_table(
        "trace_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_trace_events_session_sequence", "trace_events", ["session_id", "sequence"])


def downgrade() -> None:
    op.drop_index("ix_trace_events_session_sequence", table_name="trace_events")
    op.drop_table("trace_events")
    op.drop_table("notifications")
    op.drop_index("ix_confirmations_session_sequence", table_name="confirmations")
    op.drop_table("confirmations")
    op.drop_table("ticket_uses")
    op.drop_index("ix_visit_summaries_user_updated", table_name="visit_summaries")
    op.drop_table("visit_summaries")
    op.drop_index("ix_allergies_user_updated", table_name="allergies")
    op.drop_table("allergies")
    op.drop_index("ix_medications_user_updated", table_name="medications")
    op.drop_table("medications")
    op.drop_index("ix_sessions_user_status", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
