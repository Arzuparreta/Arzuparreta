from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import IngestOffset, Log, Source, SourceType
from db.session import session_scope
from ingestor.parsed_service_fields import docker_service_key_label
from logpilot.settings import get_settings

logger = logging.getLogger(__name__)


async def fetch_docker_id_to_name() -> dict[str, str]:
    """Map full container ID -> first name (no leading slash), via read-only Engine API."""
    settings = get_settings()
    if not settings.docker_enrich_container_names:
        return {}
    sock = Path(settings.docker_socket_path)
    if not sock.is_socket():
        return {}

    transport = httpx.AsyncHTTPTransport(uds=sock)
    try:
        async with httpx.AsyncClient(transport=transport, timeout=10.0) as client:
            r = await client.get("http://localhost/containers/json")
            r.raise_for_status()
            data = r.json()
    except (httpx.HTTPError, OSError) as exc:
        logger.debug("docker /containers/json unavailable: %s", exc)
        return {}

    out: dict[str, str] = {}
    if not isinstance(data, list):
        return out
    for c in data:
        if not isinstance(c, dict):
            continue
        cid = c.get("Id")
        if not cid or not isinstance(cid, str):
            continue
        names = c.get("Names") or []
        if not names or not isinstance(names, list):
            continue
        first = names[0]
        if not isinstance(first, str):
            continue
        out[cid] = first.lstrip("/")
    return out


def _discover_json_logs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    try:
        for d in root.iterdir():
            if not d.is_dir():
                continue
            for f in d.glob("*-json.log"):
                out.append(f)
    except OSError as exc:
        logger.warning("list %s: %s", root, exc)
    return sorted(out)


def _container_id_from_path(path: Path) -> str:
    return path.parent.name


def _parse_line(line: bytes) -> tuple[datetime, str, dict[str, Any]] | None:
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeError) as exc:
        logger.debug("skip bad json line: %s", exc)
        return None
    ts_raw = obj.get("time")
    if not ts_raw:
        return None
    try:
        ts_str = str(ts_raw).replace("Z", "+00:00")
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    raw = obj.get("log")
    if raw is None:
        raw = ""
    if not isinstance(raw, str):
        raw = str(raw)
    stream = obj.get("stream", "")
    parsed: dict[str, Any] = {"stream": stream}
    return ts, raw, parsed


async def _upsert_source(session: AsyncSession, name: str, stype: str) -> None:
    stmt = (
        pg_insert(Source)
        .values(name=name, type=stype, last_ingested_at=func.now())
        .on_conflict_do_update(
            index_elements=[Source.name],
            set_={"last_ingested_at": func.now()},
        )
    )
    await session.execute(stmt)


def _read_file_chunk(path: Path, start_offset: int) -> tuple[bytes, int, int]:
    """Returns (new_bytes, st_size, inode)."""
    st = path.stat()
    inode = int(st.st_ino)
    size = st.st_size
    with path.open("rb") as f:
        f.seek(start_offset)
        data = f.read()
    return data, size, inode


def _ingest_one_file(
    path: Path,
    source_name: str,
    saved_offset: int | None,
    saved_inode: int | None,
    carry_in: bytes,
    *,
    container_id: str,
    resolved_name: str | None,
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
        logger.info("log file inode changed, reset offset: %s", path)

    if size < offset:
        offset = 0
        carry = b""
        logger.info("log file shrank, reset offset: %s", path)

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
    for line in lines:
        parsed = _parse_line(line)
        if not parsed:
            continue
        ts, raw, meta = parsed
        meta = {
            **meta,
            "container_id": container_id,
            "logfile": logfile,
        }
        if resolved_name:
            meta["container_name"] = resolved_name
        sk, sl = docker_service_key_label(resolved_name, container_id)
        meta["service_key"] = sk
        meta["service_label"] = sl
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


class DockerLogIngestor:
    """Reads Docker JSON log files; keeps partial-line carry state per path on this instance."""

    def __init__(self) -> None:
        self._carry: dict[str, bytes] = {}

    async def ingest_tick(self) -> None:
        settings = get_settings()
        root = Path(settings.docker_log_root)
        if not root.exists():
            logger.warning("DOCKER_LOG_ROOT does not exist: %s", root)
            return

        paths = _discover_json_logs(root)
        if not paths:
            logger.debug("no *-json.log files under %s", root)
            return

        id_to_name = await fetch_docker_id_to_name()

        for path in paths:
            try:
                async with session_scope() as session:
                    await self._ingest_single_path(session, path, id_to_name)
            except Exception:
                logger.warning("ingest failed for %s", path, exc_info=True)

    async def _ingest_single_path(
        self,
        session: AsyncSession,
        path: Path,
        id_to_name: dict[str, str],
    ) -> None:
        cid = _container_id_from_path(path)
        resolved = id_to_name.get(cid)
        display = resolved if resolved else cid[:12]
        source_name = f"docker:{display}"[:512]
        await _upsert_source(session, source_name, SourceType.docker.value)

        key = str(path.resolve())
        q = await session.execute(select(IngestOffset).where(IngestOffset.path == key))
        row = q.scalar_one_or_none()
        saved_offset = int(row.offset) if row else None
        saved_inode = int(row.inode) if row and row.inode is not None else None

        carry_in = self._carry.get(key, b"")

        def work() -> tuple[list[Log], int, int | None, bytes]:
            return _ingest_one_file(
                path,
                source_name,
                saved_offset,
                saved_inode,
                carry_in,
                container_id=cid,
                resolved_name=resolved,
            )

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


_default_ingestor = DockerLogIngestor()


async def ingest_tick() -> None:
    await _default_ingestor.ingest_tick()
