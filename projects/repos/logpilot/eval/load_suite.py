from __future__ import annotations

import json
from pathlib import Path

from eval.models import SuiteItem


def load_suite(path: Path) -> list[SuiteItem]:
    """Load a JSON suite file (see eval/suites/README.md for schema)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("suite root must be a JSON object")
    items = raw.get("items")
    if not isinstance(items, list):
        raise ValueError("suite must contain an 'items' array")
    out: list[SuiteItem] = []
    for i, row in enumerate(items):
        if not isinstance(row, dict):
            raise ValueError(f"items[{i}] must be an object")
        qid = row.get("id")
        q = row.get("question")
        if not isinstance(qid, str) or not qid.strip():
            raise ValueError(f"items[{i}].id must be a non-empty string")
        if not isinstance(q, str) or not q.strip():
            raise ValueError(f"items[{i}].question must be a non-empty string")
        tags = row.get("tags", [])
        if tags is None:
            tag_t: tuple[str, ...] = ()
        elif isinstance(tags, list):
            tag_t = tuple(str(t) for t in tags)
        else:
            raise ValueError(f"items[{i}].tags must be a list of strings or null")
        ss = row.get("source_scope")
        if ss is not None and ss not in ("all", "journal", "docker", "file"):
            raise ValueError(f"items[{i}].source_scope invalid: {ss!r}")
        tk = row.get("top_k")
        if tk is not None and (not isinstance(tk, int) or tk < 1):
            raise ValueError(f"items[{i}].top_k must be a positive int or null")
        out.append(
            SuiteItem(
                id=qid.strip(),
                question=q.strip(),
                tags=tag_t,
                since=row.get("since") if isinstance(row.get("since"), str) else None,
                top_k=tk if isinstance(tk, int) else None,
                source_scope=ss if isinstance(ss, str) else None,
                min_level=row.get("min_level") if isinstance(row.get("min_level"), str) else None,
                source_contains=(
                    row.get("source_contains")
                    if isinstance(row.get("source_contains"), str)
                    else None
                ),
                use_intent=bool(row.get("use_intent", True)),
                agent=bool(row.get("agent", False)),
            ),
        )
    return out
