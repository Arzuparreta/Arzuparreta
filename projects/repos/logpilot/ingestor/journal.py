"""Ingest systemd journal via `journalctl --follow --output=json` subprocess."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import JournalCursor, Log, SourceType
from db.session import session_scope
from ingestor.docker_json import _upsert_source
from ingestor.parsed_service_fields import journal_service_key_label
from logpilot.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_PRIO_TO_LEVEL = ("emerg", "alert", "crit", "err", "warning", "notice", "info", "debug")

_JOURNAL_DUP_PLAINTEXT_PATHS: frozenset[str] = frozenset({"/var/log/syslog", "/var/log/messages"})


def journal_plaintext_omit_paths(settings: Settings) -> frozenset[str] | None:
    """When journal is on, omit file paths that duplicate journal→rsyslog forwarding (unless override)."""
    if not settings.journal_ingest or settings.text_log_include_journal_duplicate_paths:
        return None
    return frozenset(_JOURNAL_DUP_PLAINTEXT_PATHS)


def machine_id_for_journal(settings: Settings) -> str:
    if settings.journal_machine_id.strip():
        return settings.journal_machine_id.strip()[:64]
    try:
        mid = Path("/etc/machine-id")
        if mid.is_file():
            return mid.read_text(encoding="utf-8").strip()[:64]
    except OSError:
        pass
    return "default"


def level_from_priority(raw: Any) -> str | None:
    if raw is None:
        return None
    try:
        i = int(str(raw))
        if 0 <= i <= 7:
            return _PRIO_TO_LEVEL[i]
    except ValueError:
        pass
    return None


def source_name_from_journal_entry(entry: dict[str, Any]) -> str:
    unit = entry.get("_SYSTEMD_UNIT") or entry.get("UNIT")
    if unit:
        return f"journal:{unit}"[:512]
    sid = entry.get("SYSLOG_IDENTIFIER")
    if sid:
        return f"journal:{sid}"[:512]
    comm = entry.get("_COMM")
    if comm:
        return f"journal:{comm}"[:512]
    return "journal:unknown"


def timestamp_from_journal_entry(entry: dict[str, Any]) -> datetime:
    rt = entry.get("__REALTIME_TIMESTAMP")
    if rt is not None:
        try:
            us = int(str(rt))
            return datetime.fromtimestamp(us / 1_000_000, tz=timezone.utc)
        except ValueError:
            pass
    return datetime.now(tz=timezone.utc)


def log_from_journal_line(line: str) -> tuple[Log, str] | None:
    line = line.strip()
    if not line:
        return None
    try:
        entry = json.loads(line)
    except json.JSONDecodeError:
        logger.debug("skip non-json journal line")
        return None
    if not isinstance(entry, dict):
        return None

    cursor = entry.get("__CURSOR__")
    if not cursor or not isinstance(cursor, str):
        return None

    msg = entry.get("MESSAGE")
    if msg is None:
        raw = ""
    elif isinstance(msg, (dict, list)):
        raw = json.dumps(msg, ensure_ascii=False)
    else:
        raw = str(msg)

    source = source_name_from_journal_entry(entry)
    level = level_from_priority(entry.get("PRIORITY"))

    systemd_unit = entry.get("_SYSTEMD_UNIT") or entry.get("UNIT")
    parsed: dict[str, Any] = {
        "journal_cursor": cursor,
        "systemd_unit": systemd_unit,
        "syslog_identifier": entry.get("SYSLOG_IDENTIFIER"),
        "_COMM": entry.get("_COMM"),
        "priority": entry.get("PRIORITY"),
    }
    # Drop empty values for cleaner JSONB
    parsed = {k: v for k, v in parsed.items() if v is not None and v != ""}

    sk, sl = journal_service_key_label(entry)
    if sk is not None:
        parsed["service_key"] = sk
    if sl is not None:
        parsed["service_label"] = sl

    log = Log(
        timestamp=timestamp_from_journal_entry(entry),
        source=source,
        level=level,
        raw=raw,
        parsed=parsed,
        embedding=None,
    )
    return log, cursor


def build_journalctl_command(settings: Settings, saved_cursor: str | None) -> list[str]:
    cmd = ["journalctl", "--follow", "--output=json", "-n", "0"]
    if settings.journal_directory.strip():
        cmd.insert(1, "--directory")
        cmd.insert(2, settings.journal_directory.strip())
    if saved_cursor:
        cmd.insert(1, f"--cursor={saved_cursor}")
    return cmd


class JournalIngestor:
    """Runs journalctl in a background task; ingest_tick only ensures it is running."""

    def __init__(self) -> None:
        self._task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    async def ensure_running(self) -> None:
        s = get_settings()
        if not s.journal_ingest:
            return

        async with self._lock:
            if self._task is not None and not self._task.done():
                return
            self._task = asyncio.create_task(self._supervise(), name="journal-ingest")

    async def _supervise(self) -> None:
        while True:
            try:
                await self._run_pipeline()
            except Exception:
                logger.exception("journal ingest pipeline exited unexpectedly")
            await asyncio.sleep(5)

    async def _run_pipeline(self) -> None:
        settings = get_settings()
        if not settings.journal_ingest:
            return

        mid = machine_id_for_journal(settings)
        saved_cursor: str | None = None
        async with session_scope() as session:
            q = await session.execute(select(JournalCursor).where(JournalCursor.machine_id == mid))
            row = q.scalar_one_or_none()
            if row:
                saved_cursor = row.cursor

        cmd = build_journalctl_command(settings, saved_cursor)
        logger.info("starting journalctl: %s", " ".join(cmd))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            logger.error("journalctl not found; install systemd/journalctl or disable JOURNAL_INGEST")
            return

        assert proc.stdout is not None
        last_cursor: str | None = saved_cursor
        batch: list[Log] = []
        flush_every = settings.journal_flush_batch_size

        async def flush() -> None:
            nonlocal batch
            if not batch or last_cursor is None:
                batch = []
                return
            b = batch
            c = last_cursor
            batch = []
            names = sorted({lg.source for lg in b})
            async with session_scope() as session:
                for name in names:
                    await _upsert_source(session, name, SourceType.journal.value)
                session.add_all(b)
                stmt = (
                    pg_insert(JournalCursor)
                    .values(machine_id=mid, cursor=c)
                    .on_conflict_do_update(
                        index_elements=[JournalCursor.machine_id],
                        set_={"cursor": c},
                    )
                )
                await session.execute(stmt)

        while True:
            line_b = await proc.stdout.readline()
            if not line_b:
                err = None
                if proc.stderr:
                    err_b = await proc.stderr.read()
                    err = err_b.decode("utf-8", errors="replace").strip() or None
                code = await proc.wait()
                await flush()
                logger.warning(
                    "journalctl exited code=%s stderr=%s",
                    code,
                    err or "",
                )
                return

            try:
                text = line_b.decode("utf-8", errors="replace")
            except UnicodeError:
                continue

            parsed = log_from_journal_line(text)
            if not parsed:
                continue
            log, cur = parsed
            batch.append(log)
            last_cursor = cur

            if len(batch) >= flush_every:
                await flush()


_default_journal = JournalIngestor()


async def ingest_tick() -> None:
    await _default_journal.ensure_running()
