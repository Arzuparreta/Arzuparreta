"""On-demand gpu_status append for the RAG answer path."""

from __future__ import annotations

import pytest

from logpilot.settings import Settings


@pytest.mark.asyncio
async def test_append_gpu_status_skips_when_intent_off() -> None:
    from query import gpu_status_on_demand as m

    a, n = await m.append_gpu_status_for_query(False)
    assert a == ""
    assert n == 0


@pytest.mark.asyncio
async def test_append_gpu_status_skips_when_settings_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import gpu_status_on_demand as m

    monkeypatch.setattr(
        "query.gpu_status_on_demand.get_settings",
        lambda: Settings(gpu_status_query_on_demand=False),
    )
    a, n = await m.append_gpu_status_for_query(True)
    assert a == ""
    assert n == 0


@pytest.mark.asyncio
async def test_append_gpu_status_uses_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import gpu_status_on_demand as m

    from tools.gpu_status import GpuStatusResult

    async def fake_run(_self: object, _params: object, *, timeout_s: float):
        from tools.contracts import ToolEvidence, ToolRun

        return ToolRun(
            evidence=ToolEvidence(
                tool_name="gpu_status",
                input_fingerprint="x",
                ok=True,
                duration_ms=1.0,
                output_bytes=10,
                failure=None,
            ),
            output=GpuStatusResult(
                backend="nvidia",
                devices=[],
                rocm_text_excerpt=None,
                collected_at="t",
                summary="test summary",
            ),
        )

    monkeypatch.setattr("query.gpu_status_on_demand.GpuStatusTool.run", fake_run)
    block, n = await m.append_gpu_status_for_query(True)
    assert n > 0
    assert "gpu_status" in block
    assert "test summary" in block
