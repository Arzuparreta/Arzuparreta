"""Append read-only `cpu_thermal` probe (loadavg + sysfs thermal) to answer prompts."""

from __future__ import annotations

import logging

from logpilot.settings import get_settings
from tools.contracts import ToolRun
from tools.cpu_thermal import CpuThermalParams, CpuThermalResult, CpuThermalTool

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 3.0


def _format_block_success(out: CpuThermalResult) -> str:
    lines: list[str] = [
        "\n\n## CPU load and thermal — read-only (`cpu_thermal`)\n\n",
        "Structured probe **`cpu_thermal`** (`/proc/loadavg` + `/sys/class/thermal/*`). "
        "Values reflect **this environment** (container cgroup / host); thermal zones may be **absent** in minimal VMs.\n\n",
        f"**Summary:** {out.summary}\n\n",
    ]
    if out.logical_cpus > 0:
        lines.append(f"- **Logical CPUs visible:** {out.logical_cpus}\n")
    if out.loadavg is not None:
        la = out.loadavg
        lines.append(
            f"- **Load average (1m / 5m / 15m):** {la.avg_1m:.2f} / {la.avg_5m:.2f} / {la.avg_15m:.2f}\n"
            f"- **Scheduler entities (runnable / total):** {la.runnable_entities} / {la.scheduling_entities}\n",
        )
    if out.thermal_zones:
        lines.append("\n| Zone | Type | Temp (°C) |\n| --- | --- | --- |\n")
        for z in out.thermal_zones[:40]:
            tc = f"{z.temp_c:.1f}" if z.temp_c is not None else ""
            lines.append(f"| `{z.zone_id}` | {z.type_label} | {tc} |\n")
        if len(out.thermal_zones) > 40:
            lines.append(f"\n*…40 of {len(out.thermal_zones)} zones shown*\n")
    return "".join(lines)


def _format_block_failure(run: ToolRun) -> str:
    fail = run.evidence.failure
    code = fail.code if fail else None
    msg = fail.message if fail else "unknown"
    return (
        "\n\n## CPU / thermal — read-only probe\n\n"
        f"**cpu_thermal** probe did not return data (`{code or 'error'}`: {msg}). "
        "**Do not invent** load or temperature numbers.\n"
    )


async def append_cpu_thermal_for_query(cpu_thermal_on_demand: bool) -> tuple[str, int]:
    """
    When intent requests CPU/thermal context and settings allow, run the allowlisted `cpu_thermal` tool.
    """
    if not cpu_thermal_on_demand:
        return "", 0
    s = get_settings()
    if not s.cpu_thermal_query_on_demand:
        return "", 0

    tool = CpuThermalTool()
    run = await tool.run(CpuThermalParams(), timeout_s=_DEFAULT_TIMEOUT_S)
    if run.evidence.ok and run.output is not None:
        block = _format_block_success(run.output)
        logger.info("cpu_thermal on-demand ok: chars=%d", len(block))
        return block, len(block)

    logger.info("cpu_thermal on-demand failed: %s", run.evidence.failure)
    block = _format_block_failure(run)
    return block, len(block)
