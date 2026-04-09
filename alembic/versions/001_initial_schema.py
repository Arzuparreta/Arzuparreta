"""initial schema

Revision ID: 001_initial
Revises:
Create Date:

"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

from db.models import EMBEDDING_DIM

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_sources_name"),
    )
    op.create_index(op.f("ix_sources_name"), "sources", ["name"], unique=False)

    op.create_table(
        "logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(length=512), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=True),
        sa.Column("raw", sa.Text(), nullable=False),
        sa.Column("parsed", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_logs_timestamp"), "logs", ["timestamp"], unique=False)
    op.create_index(op.f("ix_logs_source"), "logs", ["source"], unique=False)
    op.create_index(
        "ix_logs_pending_embedding",
        "logs",
        ["id"],
        unique=False,
        postgresql_where=sa.text("embedding IS NULL"),
    )

    op.create_table(
        "ingest_offsets",
        sa.Column("path", sa.String(length=2048), nullable=False),
        sa.Column("offset", sa.BigInteger(), nullable=False),
        sa.Column("inode", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("path"),
    )


def downgrade() -> None:
    op.drop_table("ingest_offsets")
    op.drop_index("ix_logs_pending_embedding", table_name="logs")
    op.drop_index(op.f("ix_logs_source"), table_name="logs")
    op.drop_index(op.f("ix_logs_timestamp"), table_name="logs")
    op.drop_table("logs")
    op.drop_index(op.f("ix_sources_name"), table_name="sources")
    op.drop_table("sources")
    op.execute("DROP EXTENSION IF EXISTS vector")
