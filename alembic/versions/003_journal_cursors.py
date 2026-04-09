"""journal cursors for journalctl follow resume

Revision ID: 003_journal_cursors
Revises: 002_embedding_failed
Create Date:

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "003_journal_cursors"
down_revision = "002_embedding_failed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "journal_cursors",
        sa.Column("machine_id", sa.String(length=64), nullable=False),
        sa.Column("cursor", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("machine_id"),
    )


def downgrade() -> None:
    op.drop_table("journal_cursors")
