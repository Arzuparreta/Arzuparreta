from __future__ import annotations

import asyncio
import glob
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import IngestOffset, Log, SourceType
from db.session import session_scope
from ingestor.docker_json import _read_file_chunk, _upsert_source
from ingestor.journal import journal_plaintext_omit_paths
from logpilot.settings import get_settings

logger = logging.getLogger(__name__)

# Default: common paths on Debian/Ubuntu/Arch-style systems; globs add rotated *.log files.
_DEFAULT_PATTERNS: tuple[str, ...] = (
    "/var/log/syslog",
    "/var/log/messages",
    "/var/log/auth.log",
    "/var/log/kern.log",
    "/var/log/daemon.log",
    "/var/log/user.log",
    "/var/log/cron.log",
    "/var/log/mail.log",
    "/var/log/*.log",
)

_ISO_START = re.compile(
    r"^(?P<iso>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)"
)
_SYSLOG_START = re.compile(
    r"^(?P<mon>[A-Za-z]{3})\s+(?P<day>\d{1,2})\s+(?P<hms>\d{2}:\d{2}:\d{2})\s+"
)


def _expand_log_paths(config: str, *, omit_paths: frozenset[str] | None = None) -> list[Path]:
    patterns = [p.strip() for p in config.split(",") if p.strip()]
    if not patterns:
        patterns = list(_DEFAULT_PATTERNS)
    out: list[Path] = []
    seen: set[str] = set()
    for pat in patterns:
        paths = glob.glob(pat) if any(ch in pat for ch in "*?[]") else ([pat] if pat else [])
        for s in paths:
            p = Path(s)
            try:
                key = str(p.resolve())
            except OSError:
                key = str(p)
            if key in seen:
                continue
            seen.add(key)
            if p.is_file():
                out.append(p)
    resolved = sorted(out, key=lambda x: str(x))
    if not omit_paths:
        return resolved
    return [p for p in resolved if str(p.resolve()) not in omit_paths]


def _parse_line_ts_and_rest(line: str) -> tuple[datetime, str]:
    """Best-effort timestamp from line start; else ingestion time."""
    line = line.strip()
    if not line:
        return datetime.now(timezone.utc), ""

    m = _ISO_START.match(line)
    if m:
        frag = m.group("iso").replace(" ", "T", 1)
        try:
            ts = datetime.fromisoformat(frag.replace("Z", "+00:00"))
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            rest = line[m.end() :].lstrip()
            return ts, rest or line
        except ValueError:
            pass

    m = _SYSLOG_START.match(line)
    if m:
        mon = m.group("mon")
        day = int(m.group("day"))
        hms = m.group("hms")
        year = datetime.now(timezone.utc).year
        try:
            ts = datetime.strptime(f"{mon} {day} {year} {hms}", "%b %d %Y %H:%M:%S")
            ts = ts.replace(tzinfo=timezone.utc)
            rest = line[m.end() :].lstrip()
            return ts, rest or line
        except ValueError:
            try:
                ts = datetime.strptime(f"{mon} {day} {year} {hms}", "%B %d %Y %H:%M:%S")
                ts = ts.replace(tzinfo=timezone.utc)
                rest = line[m.end() :].lstrip()
                return ts, rest or line
            except ValueError:
                pass

    now = datetime.now(timezone.utc)
    return now, line


def _ingest_one_plain_file(
    path: Path,
    source_name: str,
    saved_offset: int | None,
    saved_inode: int | None,
    carry_in: bytes,
) -> tuple[list[Log], int, int | None, bytes]:
    try:
        st = path.stat()
    except OSError as exc:
        logger.warning("stat %s: %s", path, exc)
        return [], 0, None, b""

    inode = int(st.st_ino)
    size = st.st_size
    offset = 0 if saved_offset is None else saved_offset
    carry = carry_in

    if saved_inode is not None and inode != saved_inode:
        offset = 0
        carry = b""
        logger.info("plain log inode changed, reset offset: %s", path)

    if size < offset:
        offset = 0
        carry = b""
        logger.info("plain log shrank, reset offset: %s", path)

    try:
        new_bytes, size2, inode2 = _read_file_chunk(path, offset)
    except OSError as exc:
        logger.warning("read %s: %s", path, exc)
        return [], offset, inode, carry

    buf = carry + new_bytes
    lines: list[bytes] = []
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        lines.append(line)

    new_carry = buf
    new_offset = size2 - len(new_carry)

    logs: list[Log] = []
    logfile = str(path.resolve())
    for line_b in lines:
        try:
            text = line_b.decode("utf-8", errors="replace")
        except UnicodeError:
            continue
        if not text.strip():
            continue
        ts, raw = _parse_line_ts_and_rest(text)
        meta: dict[str, Any] = {"logfile": logfile}
        logs.append(
            Log(
                timestamp=ts,
                source=source_name,
                level=None,
                raw=raw,
                parsed=meta,
                embedding=None,
            )
        )

    return logs, new_offset, inode2, new_carry


class PlainTextLogIngestor:
    """Tails plain-text host log files (syslog-style paths) with per-path carry + offsets."""

    def __init__(self) -> None:
        self._carry: dict[str, bytes] = {}

    async def ingest_tick(self) -> None:
        s = get_settings()
        if not s.text_log_ingest:
            return

        omit = journal_plaintext_omit_paths(s)
        paths = await asyncio.to_thread(_expand_log_paths, s.text_log_paths, omit_paths=omit)
        if not paths:
            logger.debug("no plain-text log files matched (see TEXT_LOG_PATHS / defaults)")
            return

        for path in paths:
            try:
                async with session_scope() as session:
                    await self._ingest_single_path(session, path)
            except Exception:
                logger.warning("plain-text ingest failed for %s", path, exc_info=True)

    async def _ingest_single_path(self, session: AsyncSession, path: Path) -> None:
        source_name = f"file:{path.resolve()}"[:512]
        await _upsert_source(session, source_name, SourceType.syslog.value)

        key = f"plain:{path.resolve()}"
        q = await session.execute(select(IngestOffset).where(IngestOffset.path == key))
        row = q.scalar_one_or_none()
        saved_offset = int(row.offset) if row else None
        saved_inode = int(row.inode) if row and row.inode is not None else None

        carry_in = self._carry.get(key, b"")

        def work() -> tuple[list[Log], int, int | None, bytes]:
            return _ingest_one_plain_file(path, source_name, saved_offset, saved_inode, carry_in)

        new_logs, new_offset, inode, carry_out = await asyncio.to_thread(work)
        self._carry[key] = carry_out

        if new_logs:
            session.add_all(new_logs)

        if inode is None:
            return

        if row is None:
            session.add(IngestOffset(path=key, offset=new_offset, inode=inode))
        else:
            row.offset = new_offset
            row.inode = inode


_default_plain = PlainTextLogIngestor()


async def ingest_tick() -> None:
    await _default_plain.ingest_tick()
