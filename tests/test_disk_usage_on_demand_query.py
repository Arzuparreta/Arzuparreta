"""On-demand disk_usage append for the RAG answer path."""

from __future__ import annotations

import pytest

from logpilot.settings import Settings


@pytest.mark.asyncio
async def test_append_disk_usage_skips_when_intent_off() -> None:
    from query import disk_usage_on_demand as m

    a, n = await m.append_disk_usage_for_query(False)
    assert a == ""
    assert n == 0


@pytest.mark.asyncio
async def test_append_disk_usage_skips_when_settings_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import disk_usage_on_demand as m

    monkeypatch.setattr(
        m,
        "get_settings",
        lambda: Settings(disk_usage_query_on_demand=False),
    )
    a, n = await m.append_disk_usage_for_query(True)
    assert a == ""
    assert n == 0


@pytest.mark.asyncio
async def test_append_disk_usage_uses_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import disk_usage_on_demand as m
    from tools.contracts import ToolEvidence, ToolRun
    from tools.disk_usage import DiskUsageResult

    async def fake_run(self: object, params: object, *, timeout_s: float) -> ToolRun:
        return ToolRun(
            evidence=ToolEvidence(
                tool_name="disk_usage",
                input_fingerprint="x",
                ok=True,
                duration_ms=1.0,
                output_bytes=10,
                failure=None,
            ),
            output=DiskUsageResult(
                mounts=[],
                collected_at="2020-01-01T00:00:00+00:00",
                summary="Disk usage: no mounts.",
            ),
        )

    monkeypatch.setattr(m, "get_settings", lambda: Settings())
    monkeypatch.setattr("query.disk_usage_on_demand.DiskUsageTool.run", fake_run)

    block, n = await m.append_disk_usage_for_query(True)
    assert n > 0
    assert "Disk usage" in block
    assert "disk_usage" in block
