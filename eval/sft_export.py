"""Export eval ``records.jsonl`` to chat JSONL for external SFT tools."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

import typer

app = typer.Typer(help="Export eval records to JSONL for supervised fine-tuning tools.")

# High-level style hint; the live answer step uses the long RAG user message, not this string.
_DEFAULT_SYSTEM = """You are Logpilot, an assistant for system administrators analyzing homelab and server logs.
Ground conclusions in the evidence you are given (log lines, tool output, probes). If evidence is missing or insufficient, say so clearly.
Do not invent specific log lines, timestamps, or PIDs. Prefer concise, actionable wording."""


def _normalize_question(q: str) -> str:
    return re.sub(r"\s+", " ", q.strip())


def _iter_record_rows(paths: list[Path]) -> Iterator[dict[str, Any]]:
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _user_content(row: dict[str, Any], *, user_field: Literal["answer_prompt", "question"]) -> str:
    if user_field == "answer_prompt":
        ap = row.get("answer_prompt")
        return ap.strip() if isinstance(ap, str) and ap.strip() else ""
    q = row.get("question")
    return q.strip() if isinstance(q, str) else ""


def export_chat_jsonl(
    records_paths: list[Path],
    out: Path,
    *,
    system: str,
    skip_errors: bool,
    dedupe_question: bool,
    user_field: Literal["answer_prompt", "question"],
) -> tuple[int, int]:
    """Write one JSON object per line: ``messages`` + optional ``metadata``. Returns (written, skipped)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    written = 0
    skipped = 0
    with out.open("w", encoding="utf-8") as fh:
        for row in _iter_record_rows(records_paths):
            if skip_errors and row.get("error"):
                skipped += 1
                continue
            ans = row.get("answer")
            if not isinstance(ans, str) or not ans.strip():
                skipped += 1
                continue
            user = _user_content(row, user_field=user_field)
            if not user:
                skipped += 1
                continue
            if dedupe_question:
                iid = row.get("item_id")
                key = str(iid) if isinstance(iid, str) and iid else _normalize_question(
                    row.get("question", "") if isinstance(row.get("question"), str) else "",
                )
                if not key:
                    skipped += 1
                    continue
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)
            messages: list[dict[str, str]] = []
            if system.strip():
                messages.append({"role": "system", "content": system.strip()})
            messages.append({"role": "user", "content": user})
            messages.append({"role": "assistant", "content": ans.strip()})
            meta = {
                "item_id": row.get("item_id"),
                "repeat_index": row.get("repeat_index"),
            }
            fh.write(
                json.dumps(
                    {"messages": messages, "metadata": meta},
                    ensure_ascii=False,
                )
                + "\n",
            )
            written += 1
    return written, skipped


@app.command()
def main(
    records: list[Path] = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        help="One or more eval records.jsonl files",
    ),
    output: Path = typer.Option(
        ...,
        "-o",
        "--output",
        help="Output JSONL path (chat messages format)",
    ),
    system_prompt: str | None = typer.Option(
        None,
        "--system-prompt",
        help="System message prepended to each example (default: built-in Logpilot-style brief)",
    ),
    system_file: Path | None = typer.Option(
        None,
        "--system-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Read system prompt from file (overrides --system-prompt)",
    ),
    skip_errors: bool = typer.Option(True, "--skip-errors/--include-errors", help="Skip rows with non-null error"),
    dedupe_question: bool = typer.Option(
        False,
        "--dedupe-question",
        help="Keep one row per suite item_id (first occurrence wins)",
    ),
    user_from: Literal["question", "answer_prompt"] = typer.Option(
        "question",
        "--user-from",
        help="User message: suite question, or full RAG answer_prompt (re-run eval with --save-prompt)",
    ),
) -> None:
    """Export eval records to chat JSONL for external fine-tuning."""
    system = _DEFAULT_SYSTEM
    if system_file is not None:
        system = system_file.read_text(encoding="utf-8")
    elif system_prompt is not None:
        system = system_prompt

    uf: Literal["answer_prompt", "question"] = "answer_prompt" if user_from == "answer_prompt" else "question"
    written, skipped = export_chat_jsonl(
        records,
        output,
        system=system,
        skip_errors=skip_errors,
        dedupe_question=dedupe_question,
        user_field=uf,
    )
    typer.echo(f"Wrote {written} examples to {output.resolve()} (skipped {skipped})")


if __name__ == "__main__":
    app()
