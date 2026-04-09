# Using eval data for model tuning (SFT)

Logpilot’s eval harness **records** `(question, answer)` pairs (and optionally the **exact RAG user message** sent to the chat model). It does **not** run weight training inside this repo. Use the export below, then train with your stack (GPU, LLaMA-Factory, Unsloth, MLX, etc.) and **import a new GGUF** into Ollama (or swap models however you deploy).

## What you have today


| Source                                            | User message in training                                   | Best for                                                                  |
| ------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------- |
| Older `records.jsonl` (no `answer_prompt`)        | Suite **question** only                                    | Style / task framing; **does not** match the long RAG prompt at inference |
| New runs with `logpilot eval run … --save-prompt` | Full `**answer_prompt`** (logs + inventory + instructions) | **Closer** to the real answer-step distribution                           |


**Labels:** Current eval answers are **model outputs**, not human gold. For best results, **edit** assistant turns (or build preference pairs for DPO) before training. Training on raw self-outputs mostly distills existing behavior.

## Export to chat JSONL

From the repo root (venv recommended):

```bash
mkdir -p datasets
.venv/bin/python scripts/export_eval_sft_dataset.py -o datasets/logpilot_sft.jsonl \
  eval/runs/<run>/records.jsonl
```

Merge several runs (e.g. multiple eval rounds):

```bash
.venv/bin/python scripts/export_eval_sft_dataset.py -o datasets/merged.jsonl \
  eval/runs/run-a/records.jsonl \
  eval/runs/run-b/records.jsonl
```

**One example per suite item** (first occurrence wins; use after merging repeats):

```bash
.venv/bin/python scripts/export_eval_sft_dataset.py --dedupe-question -o datasets/deduped.jsonl \
  eval/runs/<run>/records.jsonl
```

**Match the real RAG prompt** (re-collect eval with `--save-prompt`, then):

```bash
.venv/bin/python scripts/export_eval_sft_dataset.py \
  --user-from answer_prompt \
  -o datasets/rag_aligned.jsonl \
  eval/runs/<run-with-prompts>/records.jsonl
```

Each output line is one JSON object: `messages` (`system` / `user` / `assistant`) plus `metadata` (`item_id`, `repeat_index`). Many trainers accept `messages` directly; strip `metadata` if your tool requires it.

## Re-collect with prompts for alignment

1. Upgrade/restart the API so it supports `include_answer_prompt` on `POST /query`.
2. Run HTTP eval with:

```bash
logpilot eval run -o eval/runs/with-prompts-1 \
     --base-url http://127.0.0.1:8080 \
     --save-prompt
```

(Add `--repeats 2` or `3` if you want more training rows per question.)

1. Export with `--user-from answer_prompt`.

## After export (outside this repo)

Typical flow:

1. Pick a **base model** compatible with your Ollama tag (e.g. same family as `CHAT_MODEL` in `.env`).
2. Run **supervised fine-tuning** on `datasets/*.jsonl` with your tool of choice.
3. **Quantize / convert** to GGUF if needed.
4. `**ollama create`** a new model from the Modelfile pointing at the new weights, or replace the model blob Ollama uses.
5. Set `**CHAT_MODEL**` (and intent model if you tune that separately) to the new name and **re-run eval** to the same suite in a **new** output directory.

Links are intentionally generic—pick a stack that matches your hardware (NVIDIA, Apple Silicon, CPU-only).

## Related code

- Export implementation: `[eval/sft_export.py](../../eval/sft_export.py)`
- CLI wrapper: `[scripts/export_eval_sft_dataset.py](../../scripts/export_eval_sft_dataset.py)`
- API field: `include_answer_prompt` on `POST /query` (`[query/api.py](../../query/api.py)`)

Decision note: `[docs/decisions/008_eval_sft_and_answer_prompt.md](../decisions/008_eval_sft_and_answer_prompt.md)`.