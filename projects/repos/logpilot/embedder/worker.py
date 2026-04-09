from __future__ import annotations

import logging

from sqlalchemy import select

from db.models import EMBEDDING_DIM, Log
from db.session import session_scope
from embedder.providers import get_embedding_provider
from logpilot.settings import get_settings

logger = logging.getLogger(__name__)


async def embed_tick() -> None:
    settings = get_settings()
    provider = await get_embedding_provider()

    async with session_scope() as session:
        stmt = (
            select(Log)
            .where(Log.embedding.is_(None))
            .where(Log.embedding_failed.is_not(True))
            .order_by(Log.id)
            .limit(settings.embed_batch_size)
        )
        rows = (await session.execute(stmt)).scalars().all()
        if not rows:
            return

        texts = [r.raw for r in rows]
        try:
            vectors = await provider.embed_many(texts)
        except Exception:
            logger.exception("embedding batch failed")
            return

        if len(vectors) != len(rows):
            logger.error(
                "embedding count mismatch: rows=%s vectors=%s",
                len(rows),
                len(vectors),
            )
        if len(vectors) > len(rows):
            logger.warning(
                "ignoring %s extra embedding vector(s)",
                len(vectors) - len(rows),
            )

        for i, row in enumerate(rows):
            if i >= len(vectors):
                logger.error("missing embedding vector for log id=%s", row.id)
                row.embedding_failed = True
                continue
            vec = vectors[i]
            if len(vec) != EMBEDDING_DIM:
                logger.error(
                    "unexpected embedding dim %s for log id=%s (expected %s)",
                    len(vec),
                    row.id,
                    EMBEDDING_DIM,
                )
                row.embedding_failed = True
                continue
            row.embedding = vec
