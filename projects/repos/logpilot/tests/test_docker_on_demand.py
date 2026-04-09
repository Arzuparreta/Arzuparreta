from __future__ import annotations

import pytest

from logpilot.settings import Settings


@pytest.mark.asyncio
async def test_append_skips_when_intent_false() -> None:
    from query import docker_on_demand as m

    a, n = await m.append_docker_engine_for_query(False)
    assert a == "" and n == 0


@pytest.mark.asyncio
async def test_append_skips_when_settings_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import docker_on_demand as m

    monkeypatch.setattr(
        "query.docker_on_demand.get_settings",
        lambda: Settings(docker_query_on_demand=False),
    )
    a, n = await m.append_docker_engine_for_query(True)
    assert a == "" and n == 0


@pytest.mark.asyncio
async def test_append_uses_fetch_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import docker_on_demand as m

    monkeypatch.setattr(
        "query.docker_on_demand.get_settings",
        lambda: Settings(docker_query_on_demand=True),
    )

    async def fake_fetch(*, settings=None, max_containers=50, timeout_s=30.0):
        return "| x |", None

    monkeypatch.setattr("query.docker_on_demand.fetch_docker_engine_summary", fake_fetch)
    a, n = await m.append_docker_engine_for_query(True)
    assert "| x |" in a
    assert n == len("| x |")


def test_format_engine_block_truncates() -> None:
    from query.docker_on_demand import _format_engine_block

    long_line = "x" * 120_000
    block = _format_engine_block(["| h |", long_line])
    assert len(block) < 120_500
    assert "truncated" in block.lower()
