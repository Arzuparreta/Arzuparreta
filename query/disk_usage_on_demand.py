"""Append read-only disk usage (`disk_usage` tool) to answer prompts when intent enables it."""

from __future__ import annotations

import logging

from logpilot.settings import get_settings
from tools.contracts import ToolRun
from tools.disk_usage import DiskUsageParams, DiskUsageResult, DiskUsageTool

logger = logging.getLogger(__name__)

_MAX_TABLE_ROWS = 40
_DEFAULT_TIMEOUT_S = 5.0


def _format_block_success(out: DiskUsageResult) -> str:
    summary = getattr(out, "summary", "")
    mounts = getattr(out, "mounts", []) or []
    lines: list[str] = [
        "\n\n## Disk usage — read-only `df` (filesystems visible in this environment)\n\n",
        "Structured probe **`disk_usage`** (`df -B1 -P`) — **filesystem capacity** (used/free/%), **not** disk I/O load "
        "or saturation. Values reflect **this process/container mount namespace**; "
        "bind-mount host paths read-only if you need the host’s view (see README / roadmap).\n\n",
        f"**Summary:** {summary}\n\n",
    ]
    if mounts:
        lines.append("| Source | Mount | Use% | Used (B) | Size (B) | Avail (B) |\n")
        lines.append("| --- | --- | --- | --- | --- | --- |\n")
        for m in mounts[:_MAX_TABLE_ROWS]:
            pct = f"{m.use_pct:.0f}%" if getattr(m, "use_pct", None) is not None else ""
            lines.append(
                f"| `{m.source}` | `{m.mountpoint}` | {pct} | {m.used_b} | {m.size_b} | {m.avail_b} |\n",
            )
        if len(mounts) > _MAX_TABLE_ROWS:
            lines.append(f"\n*…{_MAX_TABLE_ROWS} of {len(mounts)} mounts shown*\n")
    return "".join(lines)


def _format_block_failure(run: ToolRun) -> str:
    ev = run.evidence
    fail = ev.failure
    code = fail.code if fail else None
    msg = fail.message if fail else "unknown"
    return (
        "\n\n## Disk usage — read-only probe\n\n"
        f"**disk_usage** probe did not return data (`{code or 'error'}`: {msg}). "
        "**Do not invent** free-space or capacity numbers.\n"
    )


async def append_disk_usage_for_query(disk_usage_on_demand: bool) -> tuple[str, int]:
    """
    When intent requests disk context and settings allow, run the allowlisted `disk_usage` tool.
    Returns (markdown_fragment, character length for inventory / trace hints).
    """
    if not disk_usage_on_demand:
        return "", 0
    s = get_settings()
    if not s.disk_usage_query_on_demand:
        return "", 0

    tool = DiskUsageTool()
    run = await tool.run(DiskUsageParams(mount_points=None), timeout_s=_DEFAULT_TIMEOUT_S)
    if run.evidence.ok and run.output is not None:
        block = _format_block_success(run.output)
        logger.info("disk_usage on-demand ok: chars=%d", len(block))
        return block, len(block)

    logger.info("disk_usage on-demand failed: %s", run.evidence.failure)
    block = _format_block_failure(run)
    return block, len(block)
