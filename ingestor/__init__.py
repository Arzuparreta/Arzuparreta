"""Log ingestion from configured sources."""

from __future__ import annotations

from ingestor.docker_json import ingest_tick as _docker_ingest_tick
from ingestor.journal import ingest_tick as _journal_ingest_tick
from ingestor.plain_text import ingest_tick as _plain_ingest_tick


async def ingest_tick() -> None:
    await _docker_ingest_tick()
    await _journal_ingest_tick()
    await _plain_ingest_tick()


__all__ = ["ingest_tick"]
