"""Roadmap Phase A: agent scope retry, embed backlog hint, evidence_summary trace."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from logpilot.settings import Settings
from query.intent import ResolvedQuery
from query.rag import _empty_retrieval_message, ask_question_resolved


@pytest.mark.asyncio
async def test_agent_retries_all_when_scoped_planner_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from query import rag

    rq = ResolvedQuery(
        question="q",
        since="1h",
        top_k=10,
        source_scope="journal",
        min_level=None,
        source_contains=None,
        include_inventory_context=False,
        is_meta_coverage_question=False,
        journalctl_on_demand=False,
        reboot_journal_focus=False,
        docker_engine_on_demand=False,
        disk_usage_on_demand=False,
        cpu_thermal_on_demand=False,
        gpu_status_on_demand=False,
        use_keyword_supplement=False,
    )

    async def fake_planner(*_a: object, **_kw: object) -> tuple[list[object], list[dict[str, object]]]:
        return [], [{"step": 0, "action": {"type": "finish"}}]

    scopes: list[str] = []

    class _SearchResult:
        def __init__(self, rows: list[object]) -> None:
            self.rows = rows
            self.duration_ms = 1.0

    fake_row = MagicMock()
    fake_row.id = 7
    fake_row.timestamp = datetime.now(timezone.utc)
    fake_row.source = "docker:svc"
    fake_row.parsed = {}
    fake_row.raw = "hello"

    async def fake_search(_q: str, params: object, **_kw: object) -> _SearchResult:
        scopes.append(getattr(params, "source_scope", ""))
        if getattr(params, "source_scope", "") == "all":
            return _SearchResult([fake_row])
        return _SearchResult([])

    async def fake_journal(*_a: object, **_kw: object) -> tuple[str, int, bool]:
        return "", 0, False

    async def fake_docker(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_disk(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_cpu(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_gpu(_: bool) -> tuple[str, int]:
        return "", 0

    prompts: list[str] = []

    async def fake_ollama(prompt: str) -> str:
        prompts.append(prompt)
        return "ok"

    monkeypatch.setattr(rag, "run_bounded_retrieval_planner", fake_planner)
    monkeypatch.setattr(rag, "search_logs", fake_search)
    monkeypatch.setattr(rag, "append_journalctl_for_query", fake_journal)
    monkeypatch.setattr(rag, "append_docker_engine_for_query", fake_docker)
    monkeypatch.setattr(rag, "append_disk_usage_for_query", fake_disk)
    monkeypatch.setattr(rag, "append_cpu_thermal_for_query", fake_cpu)
    monkeypatch.setattr(rag, "append_gpu_status_for_query", fake_gpu)
    monkeypatch.setattr(rag, "ollama_answer", fake_ollama)
    monkeypatch.setattr(rag, "_pending_embed_count_in_window", lambda **_: 0)
    monkeypatch.setattr(
        rag,
        "get_settings",
        lambda: Settings(query_agent_max_steps=4),
    )

    result = await ask_question_resolved(rq, user_text="x", agent=True, debug=True)
    assert result.answer == "ok"
    assert scopes == ["all"]
    assert result.trace is not None
    notes = [s.get("note") for s in result.trace if isinstance(s, dict)]
    assert "retry_after_empty_scoped_agent_search" in notes
    summaries = [s for s in result.trace if isinstance(s, dict) and s.get("step") == "evidence_summary"]
    assert len(summaries) == 1
    assert summaries[0].get("agent_empty_scope_retry") is True
    assert summaries[0].get("broadened_scope_after_empty") is True
    assert prompts and "hello" in prompts[0]


def test_empty_retrieval_embed_backlog_sentence() -> None:
    rq = ResolvedQuery(
        question="q",
        since="1h",
        top_k=5,
        source_scope="all",
        min_level=None,
        source_contains=None,
        include_inventory_context=False,
        is_meta_coverage_question=False,
        journalctl_on_demand=False,
        reboot_journal_focus=False,
        docker_engine_on_demand=False,
        disk_usage_on_demand=False,
        cpu_thermal_on_demand=False,
        gpu_status_on_demand=False,
        use_keyword_supplement=False,
    )
    msg = _empty_retrieval_message(rq, [], embed_pending_in_window=3)
    assert "3" in msg
    assert "embed" in msg.lower()


@pytest.mark.asyncio
async def test_evidence_summary_in_debug_trace_non_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    from query import rag

    rq = ResolvedQuery(
        question="q",
        since="1h",
        top_k=5,
        source_scope="all",
        min_level=None,
        source_contains=None,
        include_inventory_context=False,
        is_meta_coverage_question=False,
        journalctl_on_demand=True,
        reboot_journal_focus=False,
        docker_engine_on_demand=True,
        disk_usage_on_demand=False,
        cpu_thermal_on_demand=False,
        gpu_status_on_demand=False,
        use_keyword_supplement=False,
    )

    async def fake_search(*_a: object, **_kw: object) -> SimpleNamespace:
        row = MagicMock()
        row.id = 99
        row.timestamp = datetime.now(timezone.utc)
        row.source = "file:x"
        row.parsed = {}
        row.raw = "line"
        return SimpleNamespace(rows=[row], duration_ms=2.0)

    async def fake_journal(*_a: object, **_kw: object) -> tuple[str, int, bool]:
        return "jout", 4, False

    async def fake_docker(_: bool) -> tuple[str, int]:
        return "dout", 3

    async def fake_disk(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_cpu(_: bool) -> tuple[str, int]:
        return "", 0

    async def fake_gpu(_: bool) -> tuple[str, int]:
        return "", 0

    monkeypatch.setattr(rag, "search_logs", fake_search)
    monkeypatch.setattr(rag, "append_journalctl_for_query", fake_journal)
    monkeypatch.setattr(rag, "append_docker_engine_for_query", fake_docker)
    monkeypatch.setattr(rag, "append_disk_usage_for_query", fake_disk)
    monkeypatch.setattr(rag, "append_cpu_thermal_for_query", fake_cpu)
    monkeypatch.setattr(rag, "append_gpu_status_for_query", fake_gpu)
    monkeypatch.setattr(rag, "ollama_answer", lambda _p: "y")
    monkeypatch.setattr(rag, "_pending_embed_count_in_window", lambda **_: 0)
    monkeypatch.setattr(rag, "get_settings", lambda: Settings())

    result = await ask_question_resolved(rq, user_text="x", agent=False, debug=True)
    assert result.trace is not None
    summ = [s for s in result.trace if s.get("step") == "evidence_summary"][0]
    assert summ["retrieved_row_ids_sample"] == [99]
    assert summ["journalctl_excerpt_chars"] == 4
    assert summ["docker_excerpt_chars"] == 3
    assert summ["gpu_status_on_demand"] is False
    assert summ["gpu_status_excerpt_chars"] == 0
