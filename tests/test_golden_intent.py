"""Golden-style intent JSON → coerced parameters (no live LLM)."""

from __future__ import annotations

import pytest

from query.intent import (
    DEFAULT_SINCE,
    DEFAULT_SOURCE_SCOPE,
    DEFAULT_TOP_K,
    parse_query_intent,
    resolve_query_params,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("model_json", "min_level", "source_contains"),
    [
        (
            '{"question":"q","since":"1h","top_k":20,"min_level":"err","source_contains":"nginx"}',
            "err",
            "nginx",
        ),
        (
            '{"question":"q","since":"30m","top_k":15,"min_level":"warning","source_contains":null}',
            "warning",
            None,
        ),
        (
            '{"question":"q","since":"24h","top_k":40,"min_level":null,"source_contains":"postgres"}',
            None,
            "postgres",
        ),
        (
            '{"question":"q","since":"7d","top_k":10,"min_level":"info","source_contains":"docker:"}',
            "info",
            "docker:",
        ),
        (
            '{"question":"q","since":"1h","top_k":20,"min_level":"debug","source_contains":"redis"}',
            "debug",
            "redis",
        ),
        (
            '{"question":"q","since":"2h","top_k":25,"min_level":"crit","source_contains":""}',
            "crit",
            None,
        ),
        (
            '{"question":"q","since":"45m","top_k":12,"min_level":"emerg","source_contains":"sshd"}',
            "emerg",
            "sshd",
        ),
        (
            '{"question":"q","since":"1h","top_k":20,"min_level":"notice","source_contains":"pihole"}',
            "notice",
            "pihole",
        ),
        (
            '{"question":"q","since":"6h","top_k":50,"min_level":"alert","source_contains":"kube"}',
            "alert",
            "kube",
        ),
        (
            '{"question":"q","since":"3h","top_k":8,"min_level":"error","source_contains":"app"}',
            "err",
            "app",
        ),
        (
            '{"question":"q","since":"90m","top_k":60,"min_level":"warn","source_contains":"db"}',
            "warning",
            "db",
        ),
        (
            '{"question":"q","since":"1h","top_k":20,"min_level":"badlevel","source_contains":"x"}',
            None,
            "x",
        ),
    ],
)
async def test_golden_parse_intent_pairs(
    monkeypatch: pytest.MonkeyPatch,
    model_json: str,
    min_level: str | None,
    source_contains: str | None,
) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return model_json

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    r = await parse_query_intent("user")
    assert r.min_level == min_level
    assert r.source_contains == source_contains


@pytest.mark.asyncio
async def test_golden_resolve_since_top_k_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_chat(messages: list[dict]) -> str:
        return (
            '{"question":"inner","since":"1h","top_k":20,"source_scope":"all",'
            '"min_level":"err","source_contains":"nginx"}'
        )

    monkeypatch.setattr("query.intent.ollama_chat", fake_chat)
    rq = await resolve_query_params(
        "x",
        since_override="48h",
        top_k_override=33,
        min_level_override="warning",
        source_contains_override="override",
        use_intent=True,
    )
    assert rq.since == "48h"
    assert rq.top_k == 33
    assert rq.min_level == "warning"
    assert rq.source_contains == "override"
    assert rq.question == "inner"


@pytest.mark.asyncio
async def test_golden_resolve_no_intent_explicit_filters() -> None:
    rq = await resolve_query_params(
        "hello",
        None,
        None,
        min_level_override="err",
        source_contains_override="journal:nginx",
        use_intent=False,
    )
    assert rq.question == "hello"
    assert rq.since == DEFAULT_SINCE
    assert rq.top_k == DEFAULT_TOP_K
    assert rq.source_scope == DEFAULT_SOURCE_SCOPE
    assert rq.min_level == "err"
    assert rq.source_contains == "journal:nginx"
    assert not rq.include_inventory_context
    assert not rq.journalctl_on_demand
    assert not rq.disk_usage_on_demand
    assert not rq.cpu_thermal_on_demand
    assert not rq.gpu_status_on_demand
    assert not rq.use_keyword_supplement
