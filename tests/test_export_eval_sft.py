"""export_eval_sft_dataset: records.jsonl → chat JSONL."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from eval.sft_export import export_chat_jsonl


@pytest.fixture
def records_file(tmp_path: Path) -> Path:
    p = tmp_path / "records.jsonl"
    rows = [
        {
            "item_id": "a",
            "repeat_index": 0,
            "question": "Q1?",
            "answer": "A1",
            "duration_ms": 1.0,
            "error": None,
            "trace": None,
        },
        {
            "item_id": "a",
            "repeat_index": 1,
            "question": "Q1?",
            "answer": "A1b",
            "duration_ms": 1.0,
            "error": None,
            "trace": None,
        },
        {
            "item_id": "b",
            "repeat_index": 0,
            "question": "Q2?",
            "answer": "",
            "duration_ms": 1.0,
            "error": "boom",
            "trace": None,
        },
    ]
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_export_skips_errors_and_empty_answers(tmp_path: Path, records_file: Path) -> None:
    out = tmp_path / "out.jsonl"
    w, s = export_chat_jsonl(
        [records_file],
        out,
        system="SYS",
        skip_errors=True,
        dedupe_question=False,
        user_field="question",
    )
    assert w == 2
    assert s == 1
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2


def test_export_dedupe_by_item_id(tmp_path: Path, records_file: Path) -> None:
    out = tmp_path / "out.jsonl"
    w, s = export_chat_jsonl(
        [records_file],
        out,
        system="",
        skip_errors=True,
        dedupe_question=True,
        user_field="question",
    )
    assert w == 1
    assert s == 2
    row = json.loads(out.read_text(encoding="utf-8").strip())
    assert row["messages"][-1]["content"] == "A1"


def test_export_answer_prompt_mode(tmp_path: Path) -> None:
    p = tmp_path / "r.jsonl"
    p.write_text(
        json.dumps(
            {
                "item_id": "x",
                "repeat_index": 0,
                "question": "Q?",
                "answer": "Ans",
                "answer_prompt": "FULL PROMPT",
                "duration_ms": 1.0,
                "error": None,
            },
        )
        + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.jsonl"
    w, _ = export_chat_jsonl(
        [p],
        out,
        system="S",
        skip_errors=True,
        dedupe_question=False,
        user_field="answer_prompt",
    )
    assert w == 1
    row = json.loads(out.read_text(encoding="utf-8").strip())
    assert row["messages"][1]["content"] == "FULL PROMPT"
