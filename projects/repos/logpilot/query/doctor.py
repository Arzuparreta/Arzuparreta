from __future__ import annotations

import asyncio
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from sqlalchemy import and_, func, select, text
from sqlalchemy.engine.url import make_url

from db.models import Log
from db.session import session_scope
from logpilot.settings import Settings, get_settings


def _print_host_env_hints(s: Settings) -> None:
    """If doctor failed, explain common docker-only .env values for host CLI users."""
    try:
        db_host = make_url(s.database_url).host
    except Exception:
        db_host = None
    if db_host == "postgres":
        print()
        print("  Hint: DATABASE_URL points at hostname `postgres` — that only works inside Docker.")
        print("        On your PC, set e.g. …@localhost:5432/logpilot (see .env.example).")
    ollama = s.ollama_base_url.lower()
    if "host.docker.internal" in ollama:
        print()
        print("  Hint: OLLAMA_BASE_URL uses host.docker.internal — often unresolved on Linux hosts.")
        print("        If Ollama runs here, use http://127.0.0.1:11434")


def _journal_directory_path(settings: Settings) -> Path | None:
    jd = (settings.journal_directory or "").strip()
    if jd:
        return Path(jd)
    return None


def journal_files_look_readable(settings: Settings) -> bool:
    """Heuristic for B6(a): ingest could plausibly read host journal files."""
    explicit = _journal_directory_path(settings)
    if explicit is not None:
        try:
            return explicit.is_dir() and os.access(explicit, os.R_OK)
        except OSError:
            return False
    fallback = Path("/var/log/journal")
    try:
        return fallback.is_dir() and os.access(fallback, os.R_OK)
    except OSError:
        return False


async def _probe_journalctl_read(settings: Settings, timeout_s: float = 3.0) -> tuple[bool, str]:
    """Non-follow journalctl; read-only sanity check when ingest is on."""
    cmd = ["journalctl", "-n", "0", "--no-pager"]
    jd = (settings.journal_directory or "").strip()
    if jd:
        cmd = ["journalctl", "--directory", jd, "-n", "0", "--no-pager"]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return False, "journalctl not executable"
    try:
        _, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return False, "journalctl timed out"
    err = err_b.decode("utf-8", errors="replace").strip() if err_b else ""
    if proc.returncode != 0:
        return False, err or f"exit {proc.returncode}"
    return True, ""


async def run_doctor(*, verbose: bool = False) -> int:
    """Print connectivity checks. Returns 0 if all critical checks pass."""
    s = get_settings()
    problems = 0

    print("logpilot doctor")
    if verbose:
        print("(verbose: extra ingestion / DB stats)")
    print("---")

    # Database
    try:
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        print("Database: OK (connected)")
    except Exception as exc:
        problems += 1
        print(f"Database: FAIL — {exc}")

    # Ollama (HTTP)
    base = s.ollama_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(base_url=base, timeout=httpx.Timeout(5.0)) as client:
            r = await client.get("/api/tags")
            r.raise_for_status()
        print(f"Ollama: OK ({base})")
    except Exception as exc:
        problems += 1
        print(f"Ollama: FAIL ({base}) — {exc}")

    # Docker log root (informational)
    root = Path(s.docker_log_root)
    if root.is_dir():
        print(f"Docker log root: OK ({root})")
    else:
        print(f"Docker log root: missing or not a directory — {root}")
        print("  (Ingest will warn until this path exists and contains *-json.log files.)")

    print("---")
    print("Ingestion / journal (informational)")

    # B1
    print(
        f"Journal continuous ingest (`JOURNAL_INGEST`): "
        f"{'ON' if s.journal_ingest else 'OFF'}",
    )
    print(
        "  Embedded `journal:` rows power historical RAG; "
        "`JOURNAL_QUERY_ON_DEMAND` only adds one-shot journalctl text when intent enables it "
        "(not a substitute for continuous ingest + embed).",
    )

    # B2
    jc_bin = shutil.which("journalctl")
    if jc_bin:
        print(f"journalctl: found ({jc_bin})")
    else:
        print("journalctl: not on PATH")
    if s.journal_ingest and not jc_bin:
        print("  WARN: JOURNAL_INGEST is on but journalctl is missing — continuous journal ingest cannot run.")

    # B3 / B4
    jd = (s.journal_directory or "").strip()
    if jd:
        p = Path(jd)
        if p.is_dir():
            ok_read = False
            try:
                ok_read = os.access(p, os.R_OK)
            except OSError:
                pass
            if ok_read:
                print(f"JOURNAL_DIRECTORY: OK (readable directory {p})")
            else:
                print(f"JOURNAL_DIRECTORY: WARN — directory exists but is not readable: {p}")
                if s.journal_ingest:
                    print("  WARN: JOURNAL_INGEST is on — fix permissions (e.g. host `systemd-journal` group).")
        else:
            print(f"JOURNAL_DIRECTORY: WARN — not a directory: {p}")
            if s.journal_ingest:
                print("  WARN: JOURNAL_INGEST is on — mount host `/var/log/journal` read-only and match this path.")
    else:
        print("JOURNAL_DIRECTORY: (empty — journalctl uses its default paths inside this environment)")
        fj = Path("/var/log/journal")
        if fj.is_dir():
            print(
                "  INFO: /var/log/journal exists — default journalctl behavior may differ inside a container "
                "vs the host unless you set JOURNAL_DIRECTORY and mount the host journal.",
            )

    if s.journal_ingest and jc_bin:
        ok_probe, probe_detail = await _probe_journalctl_read(s)
        if ok_probe:
            print("journalctl probe: OK (read-only `-n 0`)")
        else:
            print(f"journalctl probe: WARN — {probe_detail or 'failed'}")

    # B5
    sock = Path(s.docker_socket_path)
    if s.docker_enrich_container_names:
        try:
            is_sock = sock.is_socket()
        except OSError:
            is_sock = False
        if is_sock:
            print(f"Docker socket (`DOCKER_SOCKET_PATH`): OK ({sock})")
        else:
            print(
                f"Docker socket: INFO — `{sock}` is not a socket; container names fall back to short IDs "
                f"(set DOCKER_ENRICH_CONTAINER_NAMES=false to silence enrichment attempts).",
            )

    if verbose:
        print("---")
        print("Verbose: database stats (last 24h by source family, pending embeddings)")
        try:
            async with session_scope() as session:
                now = datetime.now(timezone.utc)
                cutoff = now - timedelta(hours=24)
                ten_min_ago = now - timedelta(minutes=10)

                j_cond = and_(Log.source.startswith("journal:"), Log.timestamp >= cutoff)
                d_cond = and_(Log.source.startswith("docker:"), Log.timestamp >= cutoff)
                f_cond = and_(Log.source.startswith("file:"), Log.timestamp >= cutoff)
                stmt = (
                    select(
                        func.count().filter(j_cond).label("journal_24h"),
                        func.count().filter(d_cond).label("docker_24h"),
                        func.count().filter(f_cond).label("file_24h"),
                        func.count()
                        .filter(and_(Log.embedding.is_(None), Log.embedding_failed.is_(False)))
                        .label("pending_embed"),
                    ).select_from(Log)
                )
                row = (await session.execute(stmt)).one()
                j24 = int(row.journal_24h or 0)
                d24 = int(row.docker_24h or 0)
                f24 = int(row.file_24h or 0)
                pend = int(row.pending_embed or 0)
                print(
                    f"  Rows in last 24h — journal: {j24:,}, docker: {d24:,}, file: {f24:,}; "
                    f"pending embed (null embedding, not failed): {pend:,}",
                )

                old_stmt = select(func.count()).select_from(Log).where(Log.timestamp < ten_min_ago)
                old_n = int((await session.execute(old_stmt)).scalar() or 0)
                has_old_logs = old_n > 0

                if (
                    s.journal_ingest
                    and journal_files_look_readable(s)
                    and j24 == 0
                    and has_old_logs
                ):
                    print(
                        "  WARN: JOURNAL_INGEST is on, journal files look readable, but no `journal:` rows "
                        "in the last 24h while older log rows exist — check journal mount, permissions, "
                        "and that migrations created `journal_cursors`.",
                    )
        except Exception as exc:
            print(f"  (Could not query stats: {exc})")

    print("---")
    if problems:
        print(f"Found {problems} problem(s). Fix the above, then try again.")
        _print_host_env_hints(s)
    else:
        print("All critical checks passed.")
    return problems
