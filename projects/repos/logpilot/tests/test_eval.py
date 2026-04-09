"""Eval harness: suite loading and runner (mocked RAG)."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from eval.load_suite import load_suite
from eval.runner import run_suite
from query.rag import QueryResult


def test_load_suite_default_file() -> None:
    path = Path("eval/suites/default_questions.json")
    items = load_suite(path)
    assert len(items) >= 10
    assert all(i.id and i.question for i in items)


def test_load_suite_validation(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"items": [{"id": "", "question": "x"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="id"):
        load_suite(bad)


@pytest.mark.asyncio
async def test_run_suite_inprocess_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    suite = tmp_path / "s.json"
    suite.write_text(
        json.dumps(
            {
                "items": [
                    {"id": "a", "question": "Q1?"},
                    {"id": "b", "question": "Q2?", "since": "1h"},
                ],
            },
        ),
        encoding="utf-8",
    )
    out = tmp_path / "run1"

    async def fake_ask(question: str, **kwargs: object) -> QueryResult:
        return QueryResult(answer=f"ans:{question}", trace=[{"mock": True}])

    monkeypatch.setattr("eval.runner.ask_question_from_prompt", fake_ask)

    records = await run_suite(
        suite,
        repeats=2,
        output_dir=out,
        base_url=None,
        debug=False,
    )
    assert len(records) == 4
    assert records[0].answer.startswith("ans:")
    assert records[0].trace is None
    lines = (out / "records.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert set(summary["items"]) == {"a", "b"}


@pytest.mark.asyncio
async def test_run_suite_max_items(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    suite = tmp_path / "s.json"
    suite.write_text(
        json.dumps(
            {
                "items": [
                    {"id": "a", "question": "Q1?"},
                    {"id": "b", "question": "Q2?"},
                ],
            },
        ),
        encoding="utf-8",
    )
    out = tmp_path / "run-max"

    async def fake_ask(question: str, **kwargs: object) -> QueryResult:
        return QueryResult(answer=f"ans:{question}", trace=None)

    monkeypatch.setattr("eval.runner.ask_question_from_prompt", fake_ask)
    records = await run_suite(
        suite,
        repeats=1,
        output_dir=out,
        base_url=None,
        debug=False,
        max_items=1,
    )
    assert len(records) == 1
    assert records[0].item_id == "a"
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["max_items"] == 1


@pytest.mark.asyncio
async def test_run_suite_debug_persists_trace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    suite = tmp_path / "s.json"
    suite.write_text(json.dumps({"items": [{"id": "x", "question": "Q"}]}), encoding="utf-8")
    out = tmp_path / "run3"

    async def fake_ask(_question: str, **kwargs: object) -> QueryResult:
        return QueryResult(answer="a", trace=[{"t": 1}])

    monkeypatch.setattr("eval.runner.ask_question_from_prompt", fake_ask)
    await run_suite(
        suite,
        repeats=1,
        output_dir=out,
        base_url=None,
        debug=True,
    )
    row = json.loads((out / "records.jsonl").read_text(encoding="utf-8").strip())
    assert row["trace"] is not None


@pytest.mark.asyncio
async def test_run_suite_inprocess_per_trial_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite = tmp_path / "s.json"
    suite.write_text(json.dumps({"items": [{"id": "slow", "question": "Q?"}]}), encoding="utf-8")
    out = tmp_path / "run-timeout"
    monkeypatch.setenv("LOGPILOT_EVAL_INPROCESS_TIMEOUT_S", "0.2")

    async def slow_ask(_question: str, **kwargs: object) -> QueryResult:
        await asyncio.sleep(60.0)
        return QueryResult(answer="never", trace=None)

    monkeypatch.setattr("eval.runner.ask_question_from_prompt", slow_ask)
    records = await run_suite(
        suite,
        repeats=1,
        output_dir=out,
        base_url=None,
        debug=False,
    )
    assert len(records) == 1
    assert records[0].error is not None
    assert "timed out" in records[0].error
    assert records[0].answer == ""

    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["inprocess_timeout_s"] == pytest.approx(0.2)
