"""One-shot `journalctl` for answers when Postgres has no embedded journal rows yet."""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from pathlib import Path

from logpilot.settings import Settings, get_settings
from query.since_parse import parse_since

logger = logging.getLogger(__name__)

_REL = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)

# journalctl --grep= extended-regex (POSIX ERE). Boot/reboot/shutdown/kernel signals.
REBOOT_JOURNAL_GREP = (
    r"reboot|systemd-shutdown|shutdown|poweroff|Linux version|Starting version|kernel:|"
    r"Watching system shutdown|Reached target.*[Ss]hutdown|systemd-journald.*stopped|"
    r"Started.*[Uu]ser.*[Mm]anager|Startup finished"
)


def journalctl_since_argument(since: str) -> str:
    """Argument for `journalctl --since=…` (relative forms when possible)."""
    raw = since.strip()
    m = _REL.match(raw.lower())
    if m:
        n = int(m.group(1))
        u = m.group(2).lower()
        unit = {"s": "s", "m": "m", "h": "h", "d": "d"}[u]
        return f"-{n}{unit}"
    dt = parse_since(since)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _journal_directory(settings: Settings) -> Path:
    d = (settings.journal_directory or "").strip()
    if d:
        return Path(d)
    return Path("/var/log/journal")


async def fetch_journalctl_excerpt(
    since: str,
    *,
    settings: Settings | None = None,
    max_lines: int = 400,
    timeout_s: float = 45.0,
    grep_pattern: str | None = None,
    kernel_only: bool = False,
) -> tuple[str | None, str | None]:
    """
    Run `journalctl` against the mounted journal directory.
    Optional `grep_pattern` is passed as `journalctl -g` (ERE) to filter messages.
    Set `kernel_only=True` for `journalctl -k` (kernel ring buffer only), e.g. as a fallback when
    full journal tails are too noisy.
    Returns (stdout, None) on success, or (None, short error reason).
    """
    s = settings or get_settings()
    if not s.journal_query_on_demand:
        return None, "disabled by JOURNAL_QUERY_ON_DEMAND=false"

    if shutil.which("journalctl") is None:
        return None, "journalctl not found in PATH"

    jdir = _journal_directory(s)
    if not jdir.is_dir():
        return None, f"journal directory not available at {jdir} (mount host /var/log or /var/log/journal read-only)"

    since_arg = journalctl_since_argument(since)
    cmd = [
        "journalctl",
        "--directory",
        str(jdir),
        "--since",
        since_arg,
        "--no-pager",
        "-n",
        str(max(1, min(max_lines, 2000))),
        "-o",
        "short-iso",
    ]
    if grep_pattern:
        cmd.extend(["-g", grep_pattern])
    if kernel_only:
        cmd.append("-k")

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=4_000_000,
            ),
            timeout=timeout_s + 5.0,
        )
    except asyncio.TimeoutError:
        return None, "journalctl subprocess timed out"

    out_b, err_b = await proc.communicate()
    out = out_b.decode("utf-8", errors="replace").strip()
    err = err_b.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        msg = err or f"exit {proc.returncode}"
        # `journalctl --grep` exits 1 when nothing matches (not a regex error); stdout is empty or "-- No entries --".
        if grep_pattern and proc.returncode == 1:
            stripped = out.strip()
            no_entries = (
                not stripped
                or stripped == "-- No entries --"
                or stripped.endswith("No entries --")
            )
            if no_entries and not err:
                logger.info("journalctl --grep: no matches (exit 1)")
                return None, "no grep matches"
        logger.warning("journalctl on-demand failed: %s", msg)
        return None, msg[:500]

    if not out:
        return None, "journalctl produced no lines (permission denied? wrong --since? empty journal?)"

    # Cap characters for LLM context
    cap = 120_000
    if len(out) > cap:
        out = out[:cap] + "\n… [truncated]\n"

    logger.info(
        "journalctl on-demand ok: since=%s grep=%s kernel=%s lines≈%d chars=%d",
        since_arg,
        bool(grep_pattern),
        kernel_only,
        out.count("\n") + 1,
        len(out),
    )
    return out, None


_LIST_BOOT_ROW = re.compile(r"^\s*-?\d+\s+[a-f0-9]{32}\b", re.IGNORECASE)


def list_boots_row_count(text: str) -> int:
    """Count data rows in `journalctl --list-boots` output (header excluded)."""
    n = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "IDX" in line and "BOOT" in line and "ID" in line:
            continue
        if _LIST_BOOT_ROW.match(line):
            n += 1
    return n


async def fetch_journalctl_list_boots(
    since: str,
    *,
    settings: Settings | None = None,
    timeout_s: float = 45.0,
) -> tuple[str | None, str | None]:
    """Run `journalctl --list-boots` for the mounted journal (best signal for reboot counts)."""
    s = settings or get_settings()
    if not s.journal_query_on_demand:
        return None, "disabled by JOURNAL_QUERY_ON_DEMAND=false"

    if shutil.which("journalctl") is None:
        return None, "journalctl not found in PATH"

    jdir = _journal_directory(s)
    if not jdir.is_dir():
        return None, f"journal directory not available at {jdir} (mount host /var/log or /var/log/journal read-only)"

    since_arg = journalctl_since_argument(since)
    cmd = [
        "journalctl",
        "--directory",
        str(jdir),
        "--since",
        since_arg,
        "--list-boots",
        "--no-pager",
    ]

    try:
        proc = await asyncio.wait_for(
            asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                limit=2_000_000,
            ),
            timeout=timeout_s + 5.0,
        )
    except asyncio.TimeoutError:
        return None, "journalctl --list-boots timed out"

    out_b, err_b = await proc.communicate()
    out = out_b.decode("utf-8", errors="replace").strip()
    err = err_b.decode("utf-8", errors="replace").strip()

    if proc.returncode != 0:
        msg = err or f"exit {proc.returncode}"
        logger.warning("journalctl --list-boots failed: %s", msg)
        return None, msg[:500]

    if not out:
        return None, "journalctl --list-boots produced no output"

    logger.info(
        "journalctl --list-boots ok: since=%s rows=%d chars=%d",
        since_arg,
        list_boots_row_count(out),
        len(out),
    )
    return out, None


def _journal_block_raw_excerpt(text: str, *, filter_note: str = "") -> str:
    return (
        "\n\n## Host systemd journal — raw `journalctl` output (read literally)\n\n"
        "What follows is **standard systemd journal text from the host OS** (services, kernel, user sessions, "
        "boot/shutdown, etc.). It was produced by running `journalctl` against the mounted journal files.\n\n"
        "**Critical:** This is **not** Logpilot “ingestion” metadata, **not** the `JOURNAL_INGEST` env var in action, "
        "**not** HTTP/API logs, and **not** academic “journal articles.” Do **not** invent a fake log format or schema. "
        "Quote or paraphrase **only** what appears in the lines. "
        "**`[GIN]`** (and similar) in multi-line logs are **Go HTTP framework** tags, not “journal ingestion” and not "
        "a product named GIN/GoInferno—do not invent frameworks.\n"
        f"{filter_note}"
        "---\n\n"
        f"{text}\n"
    )


def _journal_block_list_boots(boots_text: str, since: str) -> str:
    since_arg = journalctl_since_argument(since)
    return (
        "\n\n## Host systemd journal — boot sessions (`journalctl --list-boots`)\n\n"
        f"This table is from **`journalctl --list-boots --since={since_arg}`** against the mounted journal files. "
        "Each **data row** is one **boot session** (one OS startup) recorded in the journal.\n\n"
        "**Reboot-style questions:** Let **N** be the number of data rows (excluding the header line). "
        "Approximate **reboot events** in the window ≈ **max(0, N − 1)**. **If N = 1**, the answer is **zero** reboots "
        "inside the window (one boot session only). "
        "**Ignore** similarity-retrieved lines (`file:`, `docker:`, package managers): they are **not** evidence of "
        "reboot count (pacman/apt hooks run on upgrades, not reboots). **`[GIN]`** is **Go HTTP**, not “journal ingestion.”\n\n"
        "---\n\n"
        f"{boots_text}\n"
    )


def _journal_block_kernel_only(text: str) -> str:
    return (
        "\n\n## Host systemd journal — kernel only (`journalctl -k`)\n\n"
        "The full journal tail was **not** used here (too noisy for boot/reboot questions). This excerpt is "
        "**kernel ring buffer** output for the same `--since` window. "
        "**Not** generic HTTP/API logs; **`[GIN]`** is a Go web framework tag if it appears in other prompt sections.\n\n"
        "---\n\n"
        f"{text}\n"
    )


async def append_journalctl_for_query(
    since: str,
    *,
    journalctl_on_demand: bool,
    reboot_journal_focus: bool,
    source_contains: str | None = None,
) -> tuple[str, int, bool]:
    """
    If intent flags request host journal context and Postgres has no embedded journal rows,
    run journalctl and return text to append to the RAG prompt, byte length for inventory hints,
    and whether `--list-boots` was used (reboot counting).
    """
    s = get_settings()
    if not s.journal_query_on_demand:
        return "", 0, False
    if not journalctl_on_demand:
        return "", 0, False

    from query.inventory import embedded_row_counts_by_family

    try:
        counts = await embedded_row_counts_by_family()
    except Exception as exc:
        logger.warning("journalctl on-demand: could not read embedded counts: %s", exc)
        counts = {"journal": 0}

    if counts.get("journal", 0) > 0:
        return "", 0, False

    text: str | None = None
    err: str | None = None

    if reboot_journal_focus:
        boots_text, berr = await fetch_journalctl_list_boots(since)
        if berr:
            logger.info("journalctl --list-boots skipped: %s", berr)
        if boots_text and list_boots_row_count(boots_text) > 0:
            block = _journal_block_list_boots(boots_text, since)
            return block, len(boots_text), True

        text, err = await fetch_journalctl_excerpt(
            since,
            grep_pattern=REBOOT_JOURNAL_GREP,
            max_lines=600,
        )
        if text:
            note = (
                "\n*(Below: `journalctl -g` filter for boot/reboot/shutdown/kernel-related lines.)*\n\n"
            )
            block = _journal_block_raw_excerpt(text, filter_note=note)
            return block, len(text), False

        logger.info("journalctl reboot: grep had no matches (%s); trying kernel-only tail", err)
        text, err = await fetch_journalctl_excerpt(since, kernel_only=True, max_lines=400)
        if text:
            block = _journal_block_kernel_only(text)
            return block, len(text), False

        logger.info("journalctl reboot: no list-boots rows, grep, or kernel output: %s", err)
        return "", 0, False

    grep = None
    if source_contains:
        # journalctl --grep uses ERE; escape user substring to a literal.
        grep = re.escape(source_contains)
    text, err = await fetch_journalctl_excerpt(since, grep_pattern=grep)

    if err:
        logger.info("journalctl on-demand not used: %s", err)
    if not text:
        return "", 0, False

    block = _journal_block_raw_excerpt(text)
    return block, len(text), False
