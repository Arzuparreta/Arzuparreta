# 008 — Eval data for SFT and `answer_prompt` exposure

## Context

Operators want to **fine-tune** (or otherwise adapt) the same chat model Logpilot uses, using **eval runs** as training data. Eval historically stored only the suite **question** and model **answer**, while the answer step actually receives a **long RAG user message** (inventory, probes, log lines, instructions).

## Decision

1. **`QueryResult.answer_prompt`** — After retrieval, persist the exact string passed to `ollama_answer` when an LLM answer is attempted (including timeout/error paths where the prompt was built). Early “no evidence” returns keep `answer_prompt=None`.

2. **`POST /query`** — Optional JSON field **`include_answer_prompt`** (default `false`). When `true`, include **`answer_prompt`** in the JSON response if present. Payloads can be large.

3. **`logpilot eval run --save-prompt`** — When set, HTTP eval sets `include_answer_prompt` on the API; **records.jsonl** gains an **`answer_prompt`** field per row. Default off to keep artifacts small.

4. **Export** — [`eval/sft_export.py`](../../eval/sft_export.py) produces chat-format JSONL for **external** trainers; documented in [`docs/eval/sft_from_eval_data.md`](../eval/sft_from_eval_data.md).

## Consequences

- Better **training–inference alignment** when using `--save-prompt` + `--user-from answer_prompt`.
- **Security / privacy:** `answer_prompt` may contain log excerpts and host hints; treat exports like sensitive operational data.
- **No in-repo training loop** — avoids pinning ML frameworks; operators choose LLaMA-Factory, MLX, etc.
