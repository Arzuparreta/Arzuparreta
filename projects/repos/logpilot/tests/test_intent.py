from __future__ import annotations

import pytest

from query.intent import (
    DEFAULT_SINCE,
    DEFAULT_SOURCE_SCOPE,
    DEFAULT_TOP_K,
    TOP_K_MAX,
    parse_query_intent,
    resolve_query_params,
)


@pytest.mark.asyncio
async def test_parse_query_intent_parses_model_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '{"question": "any errors", "since": "30m", "top_k": 12}'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("any errors in the last 30m")
    assert r.question == "any errors"
    assert r.since == "30m"
    assert r.top_k == 12
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_parse_query_intent_tolerates_leading_prose(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            'Here is the JSON you asked for:\n\n{"question": "what logs exist", '
            '"since": "1h", "top_k": 25, "source_scope": "all", '
            '"min_level": null, "source_contains": null}\n'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("What logs do you have?")
    assert r.question == "what logs exist"
    assert r.top_k == 25
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_parse_query_intent_strips_markdown_fence(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '```json\n{"question": "x", "since": "2h", "top_k": 20}\n```'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("hello")
    assert r.question == "x"
    assert r.since == "2h"
    assert r.top_k == 20
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_parse_query_intent_invalid_since_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '{"question": "q", "since": "not-a-valid-window", "top_k": 5}'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("hello")
    assert r.since == DEFAULT_SINCE
    assert r.top_k == 5
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_parse_query_intent_top_k_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '{"question": "q", "since": "1h", "top_k": 999}'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("hello")
    assert r.top_k == TOP_K_MAX
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_parse_query_intent_empty_text() -> None:
    r = await parse_query_intent("   ")
    assert r.question == ""
    assert r.since == DEFAULT_SINCE
    assert r.top_k == DEFAULT_TOP_K
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_parse_query_intent_model_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(messages: list[dict]) -> str:
        raise RuntimeError("ollama down")

    monkeypatch.setattr("query.intent.ollama_chat", boom)
    r = await parse_query_intent("what failed")
    assert r.question == "what failed"
    assert r.since == DEFAULT_SINCE
    assert r.top_k == DEFAULT_TOP_K
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_parse_query_intent_source_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question": "sshd", "since": "1h", "top_k": 10, "source_scope": "journal"}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("sshd in journal")
    assert r.source_scope == "journal"


@pytest.mark.asyncio
async def test_resolve_query_params_no_intent() -> None:
    rq = await resolve_query_params(
        " raw question ",
        since_override="3h",
        top_k_override=10,
        use_intent=False,
    )
    assert rq.question == "raw question"
    assert rq.since == "3h"
    assert rq.top_k == 10
    assert rq.source_scope == DEFAULT_SOURCE_SCOPE
    assert not rq.include_inventory_context
    assert not rq.is_meta_coverage_question
    assert not rq.journalctl_on_demand
    assert not rq.reboot_journal_focus
    assert not rq.docker_engine_on_demand
    assert not rq.disk_usage_on_demand
    assert not rq.cpu_thermal_on_demand
    assert not rq.gpu_status_on_demand
    assert not rq.use_keyword_supplement


@pytest.mark.asyncio
async def test_resolve_query_params_no_intent_defaults() -> None:
    rq = await resolve_query_params("hello", None, None, use_intent=False)
    assert rq.question == "hello"
    assert rq.since == DEFAULT_SINCE
    assert rq.top_k == DEFAULT_TOP_K
    assert rq.source_scope == DEFAULT_SOURCE_SCOPE
    assert not rq.include_inventory_context
    assert not rq.journalctl_on_demand
    assert not rq.use_keyword_supplement


@pytest.mark.asyncio
async def test_resolve_query_params_overrides_after_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '{"question": "inner", "since": "1h", "top_k": 20, "source_scope": "docker"}'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params(
        "user text",
        since_override="24h",
        top_k_override=5,
        source_scope_override="journal",
        use_intent=True,
    )
    assert rq.question == "inner"
    assert rq.since == "24h"
    assert rq.top_k == 5
    assert rq.source_scope == "journal"


@pytest.mark.asyncio
async def test_parse_query_intent_invalid_source_scope_normalized(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '{"question": "q", "since": "1h", "top_k": 5, "source_scope": "containers"}'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("hello")
    assert r.source_scope == DEFAULT_SOURCE_SCOPE


@pytest.mark.asyncio
async def test_resolve_query_params_uses_intent_source_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '{"question": "x", "since": "1h", "top_k": 20, "source_scope": "file"}'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params("q", None, None, use_intent=True)
    assert rq.source_scope == "file"


@pytest.mark.asyncio
async def test_resolve_query_params_since_override_beats_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return '{"question": "q", "since": "1h", "top_k": 20}'

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params(
        "errors in the last 10 days",
        since_override="2h",
        top_k_override=None,
        use_intent=True,
    )
    assert rq.since == "2h"


@pytest.mark.asyncio
async def test_resolve_query_params_intent_booleans(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"q","since":"1h","top_k":20,"source_scope":"all",'
            '"min_level":null,"source_contains":null,'
            '"include_inventory_context":true,"is_meta_coverage_question":true,'
            '"journalctl_on_demand":true,"reboot_journal_focus":true,'
            '"docker_engine_on_demand":false,"disk_usage_on_demand":false,'
            '"cpu_thermal_on_demand":false,"gpu_status_on_demand":false,"use_keyword_supplement":false}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params("x", None, None, use_intent=True)
    assert rq.include_inventory_context is True
    assert rq.is_meta_coverage_question is True
    assert rq.journalctl_on_demand is True
    assert rq.reboot_journal_focus is True
    assert rq.docker_engine_on_demand is True
    assert rq.disk_usage_on_demand is True
    assert rq.cpu_thermal_on_demand is True
    assert rq.gpu_status_on_demand is True
    assert rq.use_keyword_supplement is False
    assert rq.top_k == 20


@pytest.mark.asyncio
async def test_resolve_query_params_docker_engine_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"restarts","since":"1d","top_k":20,"source_scope":"docker",'
            '"min_level":null,"source_contains":null,'
            '"include_inventory_context":true,"is_meta_coverage_question":false,'
            '"journalctl_on_demand":false,"reboot_journal_focus":false,'
            '"docker_engine_on_demand":true,"disk_usage_on_demand":false,'
            '"cpu_thermal_on_demand":false,"gpu_status_on_demand":false,"use_keyword_supplement":false}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params("container reboots today", None, None, use_intent=True)
    assert rq.docker_engine_on_demand is True
    assert rq.reboot_journal_focus is False
    assert rq.source_scope == "docker"


@pytest.mark.asyncio
async def test_resolve_query_params_disk_usage_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"disk","since":"1h","top_k":20,"source_scope":"all",'
            '"min_level":null,"source_contains":null,'
            '"include_inventory_context":true,"is_meta_coverage_question":false,'
            '"journalctl_on_demand":false,"reboot_journal_focus":false,'
            '"docker_engine_on_demand":false,"disk_usage_on_demand":true,'
            '"cpu_thermal_on_demand":false,"gpu_status_on_demand":false,"use_keyword_supplement":false}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params("how full is /", None, None, use_intent=True)
    assert rq.disk_usage_on_demand is True
    assert rq.docker_engine_on_demand is False


def test_inventory_coverage_heuristic_phrases() -> None:
    from query import intent as intent_mod

    assert intent_mod._inventory_coverage_heuristic(
        "Tell me all the data from my machine that you have acess to",
    ) == (True, True)
    assert intent_mod._inventory_coverage_heuristic("any errors in nginx in the last hour?") == (False, False)
    assert intent_mod._inventory_coverage_heuristic(
        "Summarize everything Logpilot can use to help me on this machine—not only similarity-retrieved log lines.",
    ) == (True, True)


@pytest.mark.asyncio
async def test_inventory_coverage_heuristic_when_intent_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"all data","since":"1h","top_k":20,"source_scope":"all",'
            '"min_level":null,"source_contains":null,'
            '"include_inventory_context":false,"is_meta_coverage_question":false,'
            '"journalctl_on_demand":false,"reboot_journal_focus":false,'
            '"docker_engine_on_demand":false,"disk_usage_on_demand":false,'
            '"cpu_thermal_on_demand":false,"gpu_status_on_demand":false,"use_keyword_supplement":true}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params(
        "Tell me all the data from my machine that you have access to",
        None,
        None,
        use_intent=True,
    )
    assert rq.include_inventory_context is True
    assert rq.is_meta_coverage_question is True
    assert rq.top_k == 20
    assert rq.use_keyword_supplement is False
    assert rq.disk_usage_on_demand is True
    assert rq.cpu_thermal_on_demand is True
    assert rq.gpu_status_on_demand is True
    assert rq.docker_engine_on_demand is True


@pytest.mark.asyncio
async def test_disk_capacity_heuristic_when_intent_wrong(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"root fs","since":"24h","top_k":20,"source_scope":"all",'
            '"min_level":null,"source_contains":null,'
            '"include_inventory_context":false,"is_meta_coverage_question":false,'
            '"journalctl_on_demand":false,"reboot_journal_focus":false,'
            '"docker_engine_on_demand":false,"disk_usage_on_demand":false,'
            '"cpu_thermal_on_demand":false,"gpu_status_on_demand":false,"use_keyword_supplement":false}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params(
        "How full is the root filesystem and should I worry?",
        None,
        None,
        use_intent=True,
    )
    assert rq.disk_usage_on_demand is True


@pytest.mark.asyncio
async def test_resolve_query_params_cpu_thermal_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"temp","since":"1h","top_k":20,"source_scope":"all",'
            '"min_level":null,"source_contains":null,'
            '"include_inventory_context":true,"is_meta_coverage_question":false,'
            '"journalctl_on_demand":false,"reboot_journal_focus":false,'
            '"docker_engine_on_demand":false,"disk_usage_on_demand":false,'
            '"cpu_thermal_on_demand":true,"gpu_status_on_demand":false,"use_keyword_supplement":false}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params("CPU temperature", None, None, use_intent=True)
    assert rq.cpu_thermal_on_demand is True
    assert rq.disk_usage_on_demand is False


@pytest.mark.asyncio
async def test_resolve_query_params_gpu_status_intent(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"gpu","since":"1h","top_k":20,"source_scope":"all",'
            '"min_level":null,"source_contains":null,'
            '"include_inventory_context":true,"is_meta_coverage_question":false,'
            '"journalctl_on_demand":false,"reboot_journal_focus":false,'
            '"docker_engine_on_demand":false,"disk_usage_on_demand":false,'
            '"cpu_thermal_on_demand":false,"gpu_status_on_demand":true,"use_keyword_supplement":false}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params("NVIDIA GPU memory use", None, None, use_intent=True)
    assert rq.gpu_status_on_demand is True
    assert rq.cpu_thermal_on_demand is False
