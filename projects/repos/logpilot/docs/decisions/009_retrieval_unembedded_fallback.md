# Decision: retrieval fallback when embeddings lag

## Context

Vector search only considers rows with `embedding IS NOT NULL`. When the embed worker is behind, operators saw empty retrieval with a hint about pending rows, even though raw log lines existed in Postgres.

## Decision

After the primary embedded search (and keyword supplement) returns **zero** rows, `search_logs` retries with the same time/source/`source_contains` filters but **without** requiring an embedding, ordered by `timestamp DESC` (capped at `top_k`). If `min_level` was set and that still yields nothing, one more pass drops `min_level` for the same unembedded query (Docker JSON logs often lack severity).

## Answer step

The final chat call for operator answers uses a dedicated **system** message (in `query/rag.py`) to discourage meta-description of evidence and common confusions (OOM vs app cleanup, GPU probe vs sudo, etc.), without changing intent/planner prompts.

## Consequences

- Answers can be grounded in **recent** unembedded lines instead of failing closed during backlog.
- Similarity ranking is skipped on that path; recency + optional error-keyword supplement applies.
