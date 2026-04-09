"""`gpu_status` tool: nvidia CSV parsing and registry wiring."""

from __future__ import annotations

import pytest

from tools.gpu_status import GpuStatusParams, GpuStatusTool, parse_nvidia_smi_csv
from tools.registry import default_tool_registry


def test_parse_nvidia_smi_csv_basic() -> None:
    text = "0, NVIDIA GeForce RTX 3080, 45, 12, 1024.0, 10240.0\n"
    devs = parse_nvidia_smi_csv(text)
    assert len(devs) == 1
    d = devs[0]
    assert d.index == 0
    assert "3080" in d.name
    assert d.temperature_c == 45.0
    assert d.utilization_gpu_pct == 12.0
    assert d.memory_used_mib == 1024.0
    assert d.memory_total_mib == 10240.0


def test_parse_nvidia_smi_csv_not_supported_temp() -> None:
    text = "0, Tesla T4, [N/A], 0, 0.0, 15360.0\n"
    devs = parse_nvidia_smi_csv(text)
    assert len(devs) == 1
    assert devs[0].temperature_c is None


@pytest.mark.asyncio
async def test_default_registry_has_gpu_status() -> None:
    reg = default_tool_registry()
    assert reg.get("gpu_status") is not None


@pytest.mark.asyncio
async def test_gpu_status_tool_runs_without_driver() -> None:
    tool = GpuStatusTool()
    run = await tool.run(GpuStatusParams(), timeout_s=2.0)
    assert run.evidence.tool_name == "gpu_status"
    # CI / laptop without nvidia-smi+driver and rocm: expect failure, not crash
    if not run.evidence.ok:
        assert run.evidence.failure is not None
