"""Add confirmation outcome and integrity metadata."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0002_confirmation_outcome"
down_revision = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("confirmations", sa.Column("card_set_id", sa.String(length=80), nullable=True))
    op.add_column("confirmations", sa.Column("card_id", sa.String(length=80), nullable=True))
    op.add_column("confirmations", sa.Column("revision", sa.Integer(), nullable=True))
    op.add_column("confirmations", sa.Column("action_hash", sa.String(length=128), nullable=True))
    op.add_column(
        "confirmations",
        sa.Column("guardian_decision_id", sa.String(length=80), nullable=True),
    )
    op.add_column("confirmations", sa.Column("state", sa.String(length=40), nullable=True))
    op.add_column("confirmations", sa.Column("idempotency_key", sa.Uuid(), nullable=True))
    op.add_column("confirmations", sa.Column("terminal_outcome", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("confirmations", "terminal_outcome")
    op.drop_column("confirmations", "idempotency_key")
    op.drop_column("confirmations", "state")
    op.drop_column("confirmations", "guardian_decision_id")
    op.drop_column("confirmations", "action_hash")
    op.drop_column("confirmations", "revision")
    op.drop_column("confirmations", "card_id")
    op.drop_column("confirmations", "card_set_id")