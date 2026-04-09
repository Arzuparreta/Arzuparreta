from __future__ import annotations

import asyncio
from pathlib import Path

import typer

from eval.runner import run_suite

eval_app = typer.Typer(
    help="Batch evaluation: run question suites against logpilot and record answers (review in Cursor or by hand).",
)


@eval_app.command("run")
def eval_run(
    suite: Path = typer.Option(
        Path("eval/suites/default_questions.json"),
        "--suite",
        "-s",
        exists=False,
        dir_okay=False,
        help="JSON suite file (see eval/suites/README.md); path must exist at run time",
    ),
    output_dir: Path = typer.Option(
        ...,
        "--output-dir",
        "-o",
        help="Directory for manifest.json, records.jsonl, summary.json",
    ),
    repeats: int = typer.Option(
        1,
        "--repeats",
        "-n",
        help="Runs per question (1–50). Default 1 for fast iteration; use 3 for variance / pre-release",
    ),
    base_url: str | None = typer.Option(
        None,
        "--base-url",
        help="If set, call POST {base_url}/query instead of in-process RAG (running API required)",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Include retrieval traces in records (larger JSONL)",
    ),
    max_items: int | None = typer.Option(
        None,
        "--max-items",
        min=1,
        help="Run only the first N suite items (smoke / faster iteration)",
    ),
    save_prompt: bool = typer.Option(
        False,
        "--save-prompt",
        help=(
            "Include answer_prompt in records.jsonl (full RAG user message sent to the chat model). "
            "Large; use for supervised fine-tuning export. HTTP mode requires a matching API version."
        ),
    ),
) -> None:
    """Run an eval suite (default: three passes per question) and write artifacts under output-dir."""

    from query.cli import _configure_cli_logging

    _configure_cli_logging()
    if repeats < 1 or repeats > 50:
        raise typer.BadParameter("repeats must be between 1 and 50", param_hint="--repeats")
    if max_items is not None and max_items < 1:
        raise typer.BadParameter("max-items must be >= 1", param_hint="--max-items")
    if not suite.is_file():
        raise typer.BadParameter(f"suite file not found: {suite}", param_hint="--suite")
    asyncio.run(
        run_suite(
            suite,
            repeats=repeats,
            output_dir=output_dir,
            base_url=base_url,
            debug=debug,
            max_items=max_items,
            save_prompt=save_prompt,
        ),
    )
    typer.echo(f"Wrote eval artifacts under {output_dir.resolve()}")
