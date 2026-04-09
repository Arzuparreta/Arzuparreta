"""Append read-only `gpu_status` probe (nvidia-smi / rocm-smi) to answer prompts."""

from __future__ import annotations

import logging

from logpilot.settings import get_settings
from tools.contracts import ToolRun
from tools.gpu_status import GpuStatusParams, GpuStatusResult, GpuStatusTool

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S = 8.0


def _format_block_success(out: GpuStatusResult) -> str:
    lines: list[str] = [
        "\n\n## GPU status — read-only (`gpu_status`)\n\n",
        "Structured probe **`gpu_status`**: fixed **`nvidia-smi`** CSV and/or **`rocm-smi`** output. "
        "Requires GPU tools in PATH; **container** deployments often need an NVIDIA/ROCm-capable image.\n\n",
        f"**Summary:** {out.summary}\n\n",
        f"- **Backend:** `{out.backend}`\n",
    ]
    if out.devices:
        lines.append("\n| GPU | Name | Temp °C | Util % | VRAM used / total (MiB) |\n| --- | --- | --- | --- | --- |\n")
        for d in out.devices[:16]:
            tc = f"{d.temperature_c:.0f}" if d.temperature_c is not None else ""
            ut = f"{d.utilization_gpu_pct:.0f}" if d.utilization_gpu_pct is not None else ""
            mem = ""
            if d.memory_used_mib is not None and d.memory_total_mib is not None:
                mem = f"{d.memory_used_mib:.0f} / {d.memory_total_mib:.0f}"
            idx = str(d.index) if d.index is not None else ""
            lines.append(f"| {idx} | {d.name} | {tc} | {ut} | {mem} |\n")
        if len(out.devices) > 16:
            lines.append(f"\n*…16 of {len(out.devices)} GPUs shown*\n")
    if out.rocm_text_excerpt:
        lines.append("\n**rocm-smi excerpt:**\n\n```text\n")
        lines.append(out.rocm_text_excerpt[:6000])
        if len(out.rocm_text_excerpt) > 6000:
            lines.append("\n…(truncated for prompt)\n")
        lines.append("\n```\n")
    return "".join(lines)


def _format_block_failure(run: ToolRun) -> str:
    fail = run.evidence.failure
    code = fail.code if fail else None
    msg = fail.message if fail else "unknown"
    return (
        "\n\n## GPU status — read-only probe\n\n"
        f"**gpu_status** probe did not return data (`{code or 'error'}`: {msg}). "
        "**Do not invent** GPU utilization, temperature, or VRAM numbers.\n"
    )


async def append_gpu_status_for_query(gpu_status_on_demand: bool) -> tuple[str, int]:
    """
    When intent requests GPU context and settings allow, run the allowlisted `gpu_status` tool.
    """
    if not gpu_status_on_demand:
        return "", 0
    s = get_settings()
    if not s.gpu_status_query_on_demand:
        return "", 0

    tool = GpuStatusTool()
    run = await tool.run(GpuStatusParams(), timeout_s=_DEFAULT_TIMEOUT_S)
    if run.evidence.ok and run.output is not None:
        block = _format_block_success(run.output)
        logger.info("gpu_status on-demand ok: chars=%d", len(block))
        return block, len(block)

    logger.info("gpu_status on-demand failed: %s", run.evidence.failure)
    block = _format_block_failure(run)
    return block, len(block)
