"""`cpu_thermal` tool: loadavg parsing and registry wiring."""

from __future__ import annotations

import pytest

from tools.cpu_thermal import CpuThermalParams, CpuThermalTool, parse_loadavg_line
from tools.registry import default_tool_registry


def test_parse_loadavg_line_golden() -> None:
    la = parse_loadavg_line("0.52 0.48 0.45 2/1234 99999\n")
    assert la is not None
    assert la.avg_1m == 0.52
    assert la.avg_5m == 0.48
    assert la.avg_15m == 0.45
    assert la.runnable_entities == 2
    assert la.scheduling_entities == 1234
    assert la.last_pid == 99999


def test_parse_loadavg_line_rejects_short() -> None:
    assert parse_loadavg_line("0.1 0.2") is None


@pytest.mark.asyncio
async def test_default_registry_has_cpu_thermal() -> None:
    reg = default_tool_registry()
    assert reg.get("cpu_thermal") is not None
    assert reg.get("disk_usage") is not None


@pytest.mark.asyncio
async def test_cpu_thermal_tool_runs() -> None:
    tool = CpuThermalTool()
    run = await tool.run(CpuThermalParams(), timeout_s=3.0)
    assert run.evidence.tool_name == "cpu_thermal"
    assert run.evidence.ok
    assert run.output is not None
    assert run.output.logical_cpus >= 0
    assert run.output.summary
