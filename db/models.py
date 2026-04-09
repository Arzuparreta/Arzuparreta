from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Optional

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base

EMBEDDING_DIM = 768


class SourceType(str, enum.Enum):
    docker = "docker"
    journal = "journal"
    pihole = "pihole"
    syslog = "syslog"


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    last_ingested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Log(Base):
    __tablename__ = "logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    raw: Mapped[str] = mapped_column(Text, nullable=False)
    parsed: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default=sa.text("'{}'::jsonb"))
    embedding: Mapped[Optional[list[float]]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    embedding_failed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.text("false")
    )


class IngestOffset(Base):
    __tablename__ = "ingest_offsets"

    path: Mapped[str] = mapped_column(String(2048), primary_key=True)
    offset: Mapped[int] = mapped_column(BigInteger, nullable=False)
    inode: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)


class JournalCursor(Base):
    """Resume token for `journalctl --follow` (separate from file-based ingest_offsets)."""

    __tablename__ = "journal_cursors"

    machine_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    cursor: Mapped[str] = mapped_column(Text, nullable=False)
