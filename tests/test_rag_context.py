from __future__ import annotations

import pytest

from query import rag
from query.rag import (
    _all_units_report_not_loaded,
    _context_annotation,
    _embed_backlog_clause,
    _no_logs_with_live_systemd_answer,
)


def test_context_annotation_joins_parsed_fields() -> None:
    assert (
        _context_annotation(
            {"container_name": "web", "systemd_unit": "nginx.service"},
        )
        == " [container_name=web; systemd_unit=nginx.service]"
    )


def test_context_annotation_prefers_service_key() -> None:
    assert (
        _context_annotation(
            {
                "service_key": "docker:web",
                "service_label": "web",
                "container_name": "web",
            },
        )
        == " [service_key=docker:web; service_label=web; container_name=web]"
    )


def test_context_annotation_service_label_when_distinct() -> None:
    assert "service_key=unit:nginx.service" in _context_annotation(
        {"service_key": "unit:nginx.service", "service_label": "nginx.service"},
    )
    assert "service_label=nginx.service" in _context_annotation(
        {"service_key": "unit:nginx.service", "service_label": "nginx.service"},
    )


def test_context_annotation_empty() -> None:
    assert _context_annotation({}) == ""


def test_embed_backlog_clause_empty_and_large() -> None:
    assert _embed_backlog_clause(0) == ""
    small = _embed_backlog_clause(3)
    assert "3 log row" in small
    large = _embed_backlog_clause(12_000)
    assert "large embedding backlog" in large
    assert "12" not in large


def test_no_logs_with_live_systemd_answer_orders_evidence() -> None:
    s = _no_logs_with_live_systemd_answer(
        source_contains="samba",
        since="1h",
        summary_line="smbd.service: ActiveState=active, SubState=running",
        embed_pending_in_window=0,
    )
    assert s.startswith("From live systemd:")
    assert "smbd.service: ActiveState=active" in s
    assert "No ingested lines matched `samba`" in s
    assert "PID 1" not in s


def test_no_logs_with_live_systemd_answer_adds_container_tip() -> None:
    s = _no_logs_with_live_systemd_answer(
        source_contains="samba",
        since="1h",
        summary_line="systemd is not usable in this runtime (no D-Bus).",
        embed_pending_in_window=0,
    )
    assert "PID 1" in s
    assert "ingested from that host" in s


def test_all_units_report_not_loaded() -> None:
    assert _all_units_report_not_loaded("a: not loaded; b: not loaded")
    assert not _all_units_report_not_loaded("a: active; b: not loaded")
    assert not _all_units_report_not_loaded("")


def test_no_logs_answer_explains_all_not_loaded() -> None:
    s = _no_logs_with_live_systemd_answer(
        source_contains="samba",
        since="1h",
        summary_line="smbd.service: not loaded; nmbd.service: not loaded",
        embed_pending_in_window=0,
    )
    assert "not loaded" in s
    assert "host systemd" in s
    assert "container" in s


async def test_ollama_answer_sends_system_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[list[dict[str, str]]] = []

    async def fake_chat(messages: list[dict[str, str]]) -> str:
        captured.append(messages)
        return "ok"

    monkeypatch.setattr(rag, "ollama_chat", fake_chat)
    out = await rag.ollama_answer("user question")
    assert out == "ok"
    assert len(captured) == 1
    msgs = captured[0]
    assert msgs[0]["role"] == "system"
    assert "concise log analyst" in msgs[0]["content"]
    assert msgs[1] == {"role": "user", "content": "user question"}
