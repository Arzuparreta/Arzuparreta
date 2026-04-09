"""Agent mode still merges on-demand journalctl when intent enables it (roadmap A4)."""

from __future__ import annotations

import pytest

from logpilot.settings import Settings
from query.intent import ResolvedQuery


@pytest.mark.asyncio
async def test_agent_mode_calls_journalctl_when_intent_on_demand(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from query import rag

    rq = ResolvedQuery(
        question="anything",
        since="1h",
        top_k=20,
        source_scope="all",
        min_level=None,
        source_contains=None,
        include_inventory_context=False,
        is_meta_coverage_question=False,
        journalctl_on_demand=True,
        reboot_journal_focus=False,
        docker_engine_on_demand=False,
        disk_usage_on_demand=False,
        cpu_thermal_on_demand=False,
        gpu_status_on_demand=False,
        use_keyword_supplement=False,
    )

    async def fake_planner(*_a: object, **_kw: object) -> tuple[list[object], list[dict[str, object]]]:
        return [], []

    journal_calls: list[bool] = []

    async def fake_journal(
        *_a: object,
        journalctl_on_demand: bool = False,
        **_kw: object,
    ) -> tuple[str, int, bool]:
        journal_calls.append(journalctl_on_demand)
        return "## journal snippet\nline", 20, False

    async def fake_docker(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_disk(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_cpu(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_gpu(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_ollama(prompt: str) -> str:
        assert "journal snippet" in prompt
        return "answered"

    monkeypatch.setattr(rag, "run_bounded_retrieval_planner", fake_planner)
    monkeypatch.setattr(rag, "append_journalctl_for_query", fake_journal)
    monkeypatch.setattr(rag, "append_docker_engine_for_query", fake_docker)
    monkeypatch.setattr(rag, "append_disk_usage_for_query", fake_disk)
    monkeypatch.setattr(rag, "append_cpu_thermal_for_query", fake_cpu)
    monkeypatch.setattr(rag, "append_gpu_status_for_query", fake_gpu)
    monkeypatch.setattr(rag, "ollama_answer", fake_ollama)
    monkeypatch.setattr(
        rag,
        "get_settings",
        lambda: Settings(query_agent_max_steps=4),
    )

    result = await rag.ask_question_resolved(rq, user_text="x", agent=True, debug=False)
    assert result.answer == "answered"
    assert journal_calls == [True]
