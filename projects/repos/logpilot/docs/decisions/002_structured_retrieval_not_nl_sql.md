# Title

Structured retrieval and bounded tools instead of raw NL→SQL

## Status

Accepted

## Context

Natural-language questions over logs could be answered by letting the LLM generate arbitrary SQL. That path is hard to bound (cost, injection, full table scans) and couples correctness to opaque model output.

## Decision

- **Retrieval stays structured:** filters (`since`, `source_scope`, `min_level`, `source_contains`, `top_k`) are validated and applied in one module (`query/retrieval.py`). The model may *suggest* parameters via JSON intent parsing or a constrained planner JSON; it does not emit raw SQL by default.
- **Optional multi-step retrieval** uses the same primitives in a bounded loop (step cap, row cap, timeout), still read-only.
- **Grounding:** answers are driven by retrieved rows (with embeddings), not invented log text.

## Consequences

- New filters require schema + SQL in one place, not ad hoc prompts.
- If structured tools are ever insufficient, a **sandboxed** NL→SQL mode would need a read-only DB role, strict `LIMIT`, and an allowlisted table set (explicitly out of scope until justified).
