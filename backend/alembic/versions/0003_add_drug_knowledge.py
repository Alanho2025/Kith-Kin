"""Add drug knowledge and interaction rules tables."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0003_add_drug_knowledge"
down_revision: str | None = "0002_confirmation_outcome"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drug_knowledge_entities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("entity_type", sa.String(length=30), nullable=False),
        sa.Column("class_name", sa.String(length=120), nullable=False),
        sa.Column("brands_or_sources", sa.JSON(), nullable=False),
        sa.Column("indications_or_use", sa.JSON(), nullable=False),
        sa.Column("warnings_or_notes", sa.JSON(), nullable=False),
        sa.Column("common_in_elderly", sa.Boolean(), nullable=False),
    )
    op.create_index(
        "ix_drug_knowledge_entities_name",
        "drug_knowledge_entities",
        ["name"],
        unique=True,
    )

    op.create_table(
        "drug_interaction_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("risk", sa.String(length=20), nullable=False),
        sa.Column("mechanism", sa.String(length=1000), nullable=False),
        sa.Column("recommendation", sa.String(length=1000), nullable=False),
        sa.Column("source", sa.String(length=200), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("drug_interaction_rules")
    op.drop_index("ix_drug_knowledge_entities_name", table_name="drug_knowledge_entities")
    op.drop_table("drug_knowledge_entities")
