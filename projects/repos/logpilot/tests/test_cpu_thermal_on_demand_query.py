"""On-demand cpu_thermal append for the RAG answer path."""

from __future__ import annotations

import pytest

from logpilot.settings import Settings


@pytest.mark.asyncio
async def test_append_cpu_thermal_skips_when_intent_off() -> None:
    from query import cpu_thermal_on_demand as m

    a, n = await m.append_cpu_thermal_for_query(False)
    assert a == ""
    assert n == 0


@pytest.mark.asyncio
async def test_append_cpu_thermal_skips_when_settings_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import cpu_thermal_on_demand as m

    monkeypatch.setattr(
        m,
        "get_settings",
        lambda: Settings(cpu_thermal_query_on_demand=False),
    )
    a, n = await m.append_cpu_thermal_for_query(True)
    assert a == ""
    assert n == 0


@pytest.mark.asyncio
async def test_append_cpu_thermal_uses_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import cpu_thermal_on_demand as m
    from tools.contracts import ToolEvidence, ToolRun
    from tools.cpu_thermal import CpuThermalResult

    async def fake_run(self: object, params: object, *, timeout_s: float) -> ToolRun:
        return ToolRun(
            evidence=ToolEvidence(
                tool_name="cpu_thermal",
                input_fingerprint="x",
                ok=True,
                duration_ms=1.0,
                output_bytes=10,
                failure=None,
            ),
            output=CpuThermalResult(
                logical_cpus=4,
                loadavg=None,
                thermal_zones=[],
                collected_at="2020-01-01T00:00:00+00:00",
                summary="CPU / thermal: test.",
            ),
        )

    monkeypatch.setattr(m, "get_settings", lambda: Settings())
    monkeypatch.setattr("query.cpu_thermal_on_demand.CpuThermalTool.run", fake_run)

    block, n = await m.append_cpu_thermal_for_query(True)
    assert n > 0
    assert "CPU load" in block
    assert "cpu_thermal" in block
