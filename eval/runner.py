from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

from eval.load_suite import load_suite
from eval.models import SuiteItem, TrialRecord
from query.rag import ask_question_from_prompt


def _eval_http_timeout() -> httpx.Timeout:
    """Bounded client wait for POST /query during eval (default below server answer timeout)."""
    read_s = float(os.environ.get("LOGPILOT_EVAL_HTTP_READ_TIMEOUT_S", "90"))
    read_s = max(15.0, min(read_s, 600.0))
    return httpx.Timeout(connect=5.0, read=read_s, write=30.0, pool=5.0)


def _eval_inprocess_timeout_s() -> float | None:
    """Wall-clock cap per in-process trial (intent + retrieval + answer). None = no asyncio cap.

    Default bounds hung stacks: a stuck DB or LLM call otherwise blocks the entire suite with an
    empty ``records.jsonl`` until the first trial completes. HTTP eval already uses httpx timeouts.
    Set ``LOGPILOT_EVAL_INPROCESS_TIMEOUT_S=0`` to disable (not recommended for long batch runs).
    """
    raw = os.environ.get("LOGPILOT_EVAL_INPROCESS_TIMEOUT_S", "180").strip()
    if raw == "0":
        return None
    try:
        v = float(raw)
    except ValueError:
        v = 180.0
    if v <= 0:
        return None
    return max(0.1, min(v, 7200.0))


async def _query_http(
    base_url: str,
    item: SuiteItem,
    *,
    debug: bool,
    save_prompt: bool,
) -> tuple[str, list[dict[str, Any]] | None, str | None, str | None]:
    url = base_url.rstrip("/") + "/query"
    body: dict[str, Any] = {
        "question": item.question,
        "use_intent": item.use_intent,
        "agent": item.agent,
        "include_answer_prompt": save_prompt,
    }
    if item.since is not None:
        body["since"] = item.since
    if item.top_k is not None:
        body["top_k"] = item.top_k
    if item.source_scope is not None:
        body["source_scope"] = item.source_scope
    if item.min_level is not None:
        body["min_level"] = item.min_level
    if item.source_contains is not None:
        body["source_contains"] = item.source_contains
    try:
        async with httpx.AsyncClient(timeout=_eval_http_timeout()) as client:
            r = await client.post(url, params={"debug": "true" if debug else "false"}, json=body)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        return "", None, str(exc), None
    ans = data.get("answer")
    if not isinstance(ans, str):
        return "", None, "response missing string answer", None
    trace = data.get("trace")
    if trace is not None and not isinstance(trace, list):
        trace = None
    ap_raw = data.get("answer_prompt")
    answer_prompt = ap_raw if isinstance(ap_raw, str) else None
    return ans, trace, None, answer_prompt


async def _query_inprocess(
    item: SuiteItem,
    *,
    debug: bool,
) -> tuple[str, list[dict[str, Any]] | None, str | None, str | None]:
    async def _call() -> tuple[str, list[dict[str, Any]] | None, str | None, str | None]:
        try:
            result = await ask_question_from_prompt(
                item.question,
                since=item.since,
                top_k=item.top_k,
                source_scope=item.source_scope,
                min_level=item.min_level,
                source_contains=item.source_contains,
                use_intent=item.use_intent,
                agent=item.agent,
                debug=debug,
            )
            return result.answer, result.trace, None, result.answer_prompt
        except Exception as exc:
            return "", None, str(exc), None

    limit = _eval_inprocess_timeout_s()
    if limit is None:
        return await _call()
    try:
        return await asyncio.wait_for(_call(), timeout=limit)
    except asyncio.TimeoutError:
        return (
            "",
            None,
            (
                f"in-process eval trial timed out after {limit:.0f}s "
                "(raise LOGPILOT_EVAL_INPROCESS_TIMEOUT_S or use --base-url for HTTP eval)"
            ),
            None,
        )


async def run_suite(
    suite_path: Path,
    *,
    repeats: int,
    output_dir: Path,
    base_url: str | None,
    debug: bool,
    max_items: int | None = None,
    save_prompt: bool = False,
) -> list[TrialRecord]:
    """Execute each suite item `repeats` times; write manifest + records + summary."""
    items = load_suite(suite_path)
    if max_items is not None:
        items = items[:max_items]
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    manifest: dict[str, Any] = {
        "run_id": run_id,
        "suite": str(suite_path.resolve()),
        "repeats": repeats,
        "mode": "http" if base_url else "inprocess",
        "base_url": base_url,
        "debug_traces": debug,
        "max_items": max_items,
        "save_prompt": save_prompt,
    }
    if base_url is None:
        manifest["inprocess_timeout_s"] = _eval_inprocess_timeout_s()
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    records: list[TrialRecord] = []
    nd_path = output_dir / "records.jsonl"

    if base_url:

        async def query_fn(
            it: SuiteItem,
        ) -> tuple[str, list[dict[str, Any]] | None, str | None, str | None]:
            return await _query_http(base_url, it, debug=debug, save_prompt=save_prompt)

    else:

        async def query_fn(
            it: SuiteItem,
        ) -> tuple[str, list[dict[str, Any]] | None, str | None, str | None]:
            return await _query_inprocess(it, debug=debug)

    with nd_path.open("w", encoding="utf-8") as nd:
        for item in items:
            for rep in range(repeats):
                t0 = time.perf_counter()
                answer, trace, err, answer_prompt = await query_fn(item)
                duration_ms = (time.perf_counter() - t0) * 1000.0
                ap = answer_prompt if save_prompt else None
                rec = TrialRecord(
                    item_id=item.id,
                    repeat_index=rep,
                    question=item.question,
                    answer=answer if err is None else "",
                    duration_ms=duration_ms,
                    error=err,
                    trace=trace if debug else None,
                    answer_prompt=ap,
                )
                records.append(rec)
                row: dict[str, Any] = {
                    "item_id": rec.item_id,
                    "repeat_index": rec.repeat_index,
                    "question": rec.question,
                    "answer": rec.answer,
                    "duration_ms": rec.duration_ms,
                    "error": rec.error,
                    "trace": rec.trace,
                }
                if save_prompt:
                    row["answer_prompt"] = rec.answer_prompt
                nd.write(json.dumps(row, ensure_ascii=False) + "\n")
                nd.flush()

    _write_summary(output_dir, records)
    return records


def _write_summary(output_dir: Path, records: list[TrialRecord]) -> None:
    by_id: dict[str, list[TrialRecord]] = defaultdict(list)
    for r in records:
        by_id[r.item_id].append(r)

    summary: dict[str, Any] = {"items": {}}
    for iid, trials in sorted(by_id.items()):
        errs = sum(1 for t in trials if t.error)
        latencies = [t.duration_ms for t in trials if t.error is None]
        item_summary: dict[str, Any] = {
            "trials": len(trials),
            "errors": errs,
        }
        if latencies:
            item_summary["latency_ms_mean"] = sum(latencies) / len(latencies)
            item_summary["latency_ms_max"] = max(latencies)
        summary["items"][iid] = item_summary

    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
