# Evaluation harness

Run many natural-language questions against logpilot, **optionally repeating each** (default **1×** for fast runs; use **`--repeats 3`** when you need flake/variance signal), and write **structured artifacts**. **Judging answers is not automated here**: you (or a Cursor agent) read `records.jsonl`, apply [`rubric.md`](rubric.md) as a checklist, change code, and re-run the eval.

**Coverage:** the full suite keeps **diversity** across question types (hardware probes, systemd services, Docker/journal/file scopes, reboots, normal and odd phrasing). Lowering repeats reduces wall time without dropping categories.

## What you edit vs what runs automatically

| Artifact | Who edits | Purpose |
|----------|-----------|---------|
| [`suites/default_questions.json`](suites/default_questions.json) | **You** | Question list + optional query overrides |
| [`rubric.md`](rubric.md) | **You** | Review checklist for humans/agents (not consumed by the CLI) |
| `eval/runs/<your-run>/` | **Automation** | `manifest.json`, `records.jsonl`, `summary.json` (gitignored) |

## CLI

From the repo root (with DB + Ollama reachable, same as `logpilot ask`):

```bash
logpilot eval run -o eval/runs/$(date +%Y%m%d-%H%M)
```

**Practical default:** if you run the stack with **Docker Compose**, prefer **`--base-url http://127.0.0.1:8080`**. That matches the API container’s DB and Ollama wiring and uses the same **bounded HTTP** timeouts as production. Host **in-process** eval needs a **host** `.env` where `DATABASE_URL` and `OLLAMA_BASE_URL` actually work; misconfigured host DB URLs often look like a “hung” run (empty `records.jsonl` for a long time).

Against a **running API** (e.g. Compose service on port 8080):

```bash
logpilot eval run -o eval/runs/http-1 --base-url http://127.0.0.1:8080
```

Use **`--max-items N`** to run only the first *N* questions (smoke tests, faster tuning).

Use **`--repeats 3`** (or **2**) before release or when debugging nondeterminism; default **1** keeps full **suite** coverage with ~3× less wall time than the old default.

HTTP mode uses a **90s read** timeout per question (5s connect). Override with `LOGPILOT_EVAL_HTTP_READ_TIMEOUT_S` if your stack is slower.

**In-process** mode applies **`LOGPILOT_EVAL_INPROCESS_TIMEOUT_S`** (default **180s**) around each full trial so a stuck LLM or DB call cannot block the entire suite indefinitely. Set to **`0`** to disable the asyncio cap (not recommended for long batches). Each finished trial is flushed to `records.jsonl` immediately so progress is visible while the run continues.

**Retrieval traces** (large JSONL):

```bash
logpilot eval run -o eval/runs/traced-1 --debug
```

**Answer prompt for fine-tuning exports** (very large JSONL; use HTTP eval against an API built from this repo; requires `include_answer_prompt` on `POST /query`):

```bash
logpilot eval run -o eval/runs/with-prompts --base-url http://127.0.0.1:8080 --save-prompt
```

## Supervised fine-tuning export

Convert `records.jsonl` to chat-format JSONL for external trainers (LLaMA-Factory, Unsloth, MLX, etc.):

```bash
mkdir -p datasets
python scripts/export_eval_sft_dataset.py -o datasets/sft.jsonl --dedupe-question eval/runs/<run>/records.jsonl
```

Details, alignment caveats, and Ollama-oriented follow-up: **[`docs/eval/sft_from_eval_data.md`](../docs/eval/sft_from_eval_data.md)**.

## Outputs

- **`manifest.json`**: suite path, repeats, mode (`inprocess` vs `http`), flags; in-process runs include `inprocess_timeout_s` (seconds, or JSON `null` when unlimited); `save_prompt` when `--save-prompt` was used.
- **`records.jsonl`**: one JSON object per trial (`item_id`, `repeat_index`, `question`, `answer`, `duration_ms`, `error`, optional `trace` if `--debug`, optional `answer_prompt` if `--save-prompt`).
- **`summary.json`**: per-`id` error counts and mean/max latency.

## Agent-oriented workflow

See **[`docs/agents/EVAL.md`](../docs/agents/EVAL.md)** for flags and artifacts. For a **full improve loop** driven by an agent, use **[`docs/agents/EVAL_LOOP_PROMPT.md`](../docs/agents/EVAL_LOOP_PROMPT.md)** (`@`-mention that file in Cursor and say “run the eval loop”).

## Related product tests

`make check` runs **offline** pytest (including eval loader/runner tests with mocks). This harness is for **live** stack evaluation against real logs and models.
