from __future__ import annotations

import asyncio
import logging

import uvicorn

from ingestor import ingest_tick
from embedder.worker import embed_tick as embed_tick_worker
from logpilot.settings import get_settings
from query.api import app as fastapi_app

logger = logging.getLogger(__name__)


async def ingest_loop() -> None:
    while True:
        try:
            await ingest_tick()
        except Exception:
            logger.exception("ingest tick failed")
        await asyncio.sleep(get_settings().ingest_poll_interval_s)


async def embed_loop() -> None:
    while True:
        try:
            await embed_tick_worker()
        except Exception:
            logger.exception("embed tick failed")
        await asyncio.sleep(get_settings().embed_poll_interval_s)


async def run_services() -> None:
    settings = get_settings()
    tasks = [
        asyncio.create_task(ingest_loop(), name="ingest"),
        asyncio.create_task(embed_loop(), name="embed"),
    ]

    if settings.logpilot_enable_api:
        cfg = uvicorn.Config(
            fastapi_app,
            host=settings.logpilot_api_host,
            port=settings.logpilot_api_port,
            log_level=settings.log_level.lower(),
        )
        server = uvicorn.Server(cfg)
        tasks.append(asyncio.create_task(server.serve(), name="api"))

    await asyncio.gather(*tasks)
