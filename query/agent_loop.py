"""Bounded multi-step retrieval planner (constrained JSON; read-only tools)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

from db.models import Log
from query.intent import SOURCE_SCOPES, TOP_K_MAX, TOP_K_MIN, ResolvedQuery
from query.levels import normalize_log_level
from query.ollama_chat import ollama_chat
from query.retrieval import SearchParams, list_distinct_sources, normalize_source_contains, search_logs

logger = logging.getLogger(__name__)

_JSON_OBJ = re.compile(r"\{[\s\S]*\}")

PLANNER_SYSTEM = """You plan read-only log retrieval steps. Output ONLY one JSON object (no markdown fences).

Keys:
- "thought": optional string, one short sentence.
- "action": object — exactly one of:
  { "type": "search_logs", "since": "<relative>", "top_k": <int>, "source_scope": "all"|"journal"|"docker"|"file", "min_level": "<level>|null", "source_contains": "<substring>|null" }
  { "type": "list_sources", "limit": <int optional> }
  { "type": "narrow_time", "since": "<relative>" }
  { "type": "finish" }

Rules:
- Use search_logs to fetch log lines (embeddings required server-side). Omit a field to reuse the current working value shown in the user message.
- Use list_sources to see distinct source names when the user did not name a service clearly.
- Use narrow_time to shorten the window (e.g. from 24h to 1h) if retrieval is too broad.
- If rows_fetched_so_far is 0 and working_source_scope is not "all", prefer one search_logs with source_scope "all" (reuse other working fields) before finish — unless list_sources is clearly needed first to disambiguate sources.
- Use finish when you have enough lines to answer or cannot improve retrieval.

Levels for min_level: emerg, alert, crit, err, warning, notice, info, debug (or null).
"""


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_planner_json(raw: str) -> dict[str, Any]:
    text = _strip_code_fence(raw)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    m = _JSON_OBJ.search(raw)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
    raise ValueError("no valid JSON object in planner output")


def _clamp_top_k(v: Any, default: int) -> int:
    if isinstance(v, int) and not isinstance(v, bool):
        return max(TOP_K_MIN, min(TOP_K_MAX, v))
    if isinstance(v, float):
        return max(TOP_K_MIN, min(TOP_K_MAX, int(v)))
    return default


def _normalize_scope(raw: Any, fallback: str) -> str:
    if isinstance(raw, str) and raw.strip().lower() in SOURCE_SCOPES:
        return raw.strip().lower()
    return fallback


async def run_bounded_retrieval_planner(
    user_text: str,
    resolved: ResolvedQuery,
    *,
    max_steps: int,
    max_total_rows: int,
    timeout_s: float,
) -> tuple[list[Log], list[dict[str, object]]]:
    """Run up to `max_steps` planner turns; merge rows by id; respect row and time budgets."""
    working_since = resolved.since
    working_scope = resolved.source_scope
    working_min = resolved.min_level
    working_src = resolved.source_contains
    working_top_k = resolved.top_k

    rows_by_id: dict[int, Log] = {}
    trace: list[dict[str, object]] = []
    deadline = time.monotonic() + max(1.0, timeout_s)

    for step_idx in range(max_steps):
        if time.monotonic() >= deadline:
            trace.append({"event": "timeout", "step": step_idx})
            break
        user_msg = (
            f"User request:\n{user_text}\n\n"
            f"Resolved defaults (from intent/overrides):\n"
            f"- question_for_search: {resolved.question}\n"
            f"- working_since: {working_since}\n"
            f"- working_top_k: {working_top_k}\n"
            f"- working_source_scope: {working_scope}\n"
            f"- working_min_level: {working_min}\n"
            f"- working_source_contains: {working_src}\n"
            f"- rows_fetched_so_far: {len(rows_by_id)}\n"
            f"- max_total_rows: {max_total_rows}\n"
            f"- step: {step_idx + 1} of {max_steps}\n"
        )

        left_s = max(0.1, deadline - time.monotonic())
        try:
            raw = await asyncio.wait_for(
                ollama_chat(
                    [
                        {"role": "system", "content": PLANNER_SYSTEM},
                        {"role": "user", "content": user_msg},
                    ],
                ),
                timeout=min(left_s, 120.0),
            )
        except asyncio.TimeoutError:
            trace.append({"event": "ollama_timeout", "step": step_idx})
            break

        try:
            data = _parse_planner_json(raw)
        except ValueError:
            logger.warning("planner JSON parse failed at step %s", step_idx)
            trace.append({"event": "bad_json", "step": step_idx, "raw": raw[:500]})
            break

        action = data.get("action")
        if not isinstance(action, dict):
            trace.append({"event": "missing_action", "step": step_idx})
            break

        atype = action.get("type")
        trace.append({"step": step_idx, "thought": data.get("thought"), "action": action})

        if atype == "finish":
            break

        if atype == "narrow_time":
            s = action.get("since")
            if isinstance(s, str) and s.strip():
                working_since = s.strip()
            continue

        if atype == "list_sources":
            lim_raw = action.get("limit")
            lim = 40
            if isinstance(lim_raw, int) and not isinstance(lim_raw, bool):
                lim = max(1, min(100, lim_raw))
            params = SearchParams(
                since=working_since,
                top_k=min(working_top_k, max_total_rows),
                source_scope=working_scope,
                min_level=working_min,
                source_contains=working_src,
            )
            names, dur_ms = await list_distinct_sources(params, limit=lim)
            trace[-1]["list_sources_result"] = {"count": len(names), "duration_ms": dur_ms, "sample": names[:15]}
            continue

        if atype == "search_logs":
            if isinstance(action.get("since"), str) and action["since"].strip():
                working_since = action["since"].strip()
            working_top_k = _clamp_top_k(action.get("top_k"), working_top_k)
            working_scope = _normalize_scope(action.get("source_scope"), working_scope)
            ml_raw = action.get("min_level")
            if ml_raw is None or (isinstance(ml_raw, str) and not ml_raw.strip()):
                pass
            else:
                working_min = normalize_log_level(ml_raw)
            sc_raw = action.get("source_contains")
            if sc_raw is None or (isinstance(sc_raw, str) and not sc_raw.strip()):
                pass
            else:
                working_src = normalize_source_contains(str(sc_raw))

            budget_left = max(0, max_total_rows - len(rows_by_id))
            tk = min(working_top_k, budget_left)
            if tk <= 0:
                trace[-1]["event"] = "row_budget_exhausted"
                break

            params = SearchParams(
                since=working_since,
                top_k=tk,
                source_scope=working_scope,
                min_level=working_min,
                source_contains=working_src,
            )
            result = await search_logs(
                resolved.question,
                params,
                keyword_supplement=resolved.use_keyword_supplement,
            )
            for r in result.rows:
                rows_by_id[r.id] = r
            trace[-1]["search_logs_result"] = {
                "row_count": len(result.rows),
                "duration_ms": result.duration_ms,
                "total_unique": len(rows_by_id),
            }
            if len(rows_by_id) >= max_total_rows:
                break
            continue

        trace.append({"event": "unknown_action", "type": atype})
        break

    return list(rows_by_id.values()), trace
