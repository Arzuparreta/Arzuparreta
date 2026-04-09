"""add log.embedding_failed for embed partial failures

Revision ID: 002_embedding_failed
Revises: 001_initial
Create Date:

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_embedding_failed"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "logs",
        sa.Column(
            "embedding_failed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.drop_index("ix_logs_pending_embedding", table_name="logs")
    op.create_index(
        "ix_logs_pending_embedding",
        "logs",
        ["id"],
        unique=False,
        postgresql_where=sa.text("embedding IS NULL AND embedding_failed IS NOT TRUE"),
    )
    op.alter_column("logs", "embedding_failed", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_logs_pending_embedding", table_name="logs")
    op.create_index(
        "ix_logs_pending_embedding",
        "logs",
        ["id"],
        unique=False,
        postgresql_where=sa.text("embedding IS NULL"),
    )
    op.drop_column("logs", "embedding_failed")
