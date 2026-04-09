# Agent guide: batch evaluation (`logpilot eval`)

## Purpose

- **Regression and tuning signal** for RAG + prompts + tools. Most iteration is **changes in this repo** (prompts, retrieval, API). Swapping the **Ollama model name** (`CHAT_MODEL`, etc.) matters only when you intentionally use **different base weights** in Ollama—not for every bugfix.
- **Repeatability**: default **1×** per question for speed; use **`--repeats 3`** when you need flake/variance (e.g. before merge). The **full suite** still exercises diverse question types (hardware, systemd, Docker, journal/file scopes, reboots, normal and odd phrasing).
- **Human / agent gate**: operators own **[`eval/suites/default_questions.json`](../../eval/suites/default_questions.json)**. **[`eval/rubric.md`](../../eval/rubric.md)** is a **review checklist** for whoever reads the run (you or a Cursor agent); the CLI does **not** call a model to score answers.

## Invoking the model

| Mode | When to use | Command hint |
|------|-------------|----------------|
| **HTTP** | **Preferred** when Compose (or any API) is up — same DB/Ollama as the running container, bounded client timeouts | `logpilot eval run --base-url http://127.0.0.1:8080 -o eval/runs/...` |
| **In-process** | Host dev only when `.env` matches a working DB + Ollama (`logpilot ask` works). Each trial is capped by `LOGPILOT_EVAL_INPROCESS_TIMEOUT_S` (default **180s**; `0` = no cap) | `logpilot eval run -o eval/runs/...` (no `--base-url`) |

Always pass **`-o` / `--output-dir`** (under `eval/runs/` is conventional; that tree is gitignored).

**HTTP eval** uses a bounded client timeout per question (see [`eval/README.md`](../../eval/README.md)); tune with `LOGPILOT_EVAL_HTTP_READ_TIMEOUT_S` if needed. **In-process** eval uses `LOGPILOT_EVAL_INPROCESS_TIMEOUT_S` per trial (see same doc). Use **`--max-items N`** for a short smoke run.

Use **`--debug`** when you need retrieval **traces inside** `records.jsonl` (larger files). Without it, traces are omitted to keep JSONL small.

Use **`--save-prompt`** (HTTP eval) when building **supervised fine-tuning** datasets: each row can include **`answer_prompt`** (the full RAG user message). Export with [`docs/eval/sft_from_eval_data.md`](../eval/sft_from_eval_data.md) and `scripts/export_eval_sft_dataset.py`.

## Review workflow (who judges?)

The harness **records** answers only; it does **not** print scores.

**You are the judge** — the human operator **or the Cursor agent** reading `records.jsonl`. That is the intended loop: compare what was **asked** vs what came **back**, call out gaps in plain language (“wanted X, got irrelevant Y”, “invented timestamps”, “good humility”), use **`eval/rubric.md`** as dimensions, then patch **code / prompts / retrieval / tools** and re-run eval to a **new** output directory.

**What we do *not* do in the CLI** ([`006_eval_no_llm_judge.md`](../decisions/006_eval_no_llm_judge.md)): wire the **same** Ollama `CHAT_MODEL` that produced the answer to **automatically** score every row in batch. That is weak and circular. **Agent review is different** — separate reasoning pass, not the harness calling the answer model as a grader.

1. Run `logpilot eval run -o <dir> ...`.
2. Open `records.jsonl` (and `summary.json` for errors/latency).
3. For each `item_id` / `repeat_index`, read `question` and `answer` (and `trace` if present). Apply **`eval/rubric.md`** (groundedness, humility, relevance, safety).
4. Change what needs fixing in-repo, run `make check`, **re-run** eval to a **new** directory, compare.

## Comparing runs

1. Sort/filter `records.jsonl` by `item_id` and `repeat_index`.
2. Use `summary.json` for quick regressions: higher `errors` or large `latency_ms_max`.
3. Keep the same suite file when comparing across commits; bump only when intentionally changing the benchmark.

## Extending beyond this harness (industry practice)

Use this project as the **execution core**, and add workflows as needed:

| Technique | Role |
|-----------|------|
| **Golden / fixture tests** | Already in `tests/` (intent, tools); keep for deterministic units. |
| **This eval suite** | Live end-to-end Q&A over real DB + embeddings + LLM. |
| **Human / Cursor review** | Read artifacts + rubric; iterate in chat or by hand. |
| **Pairwise / side-by-side** | Export two `records.jsonl` and compare answers for the same `item_id` (manual or script). |
| **Regression baselines** | Check in **small** `summary.json` snapshots or CSV extracts—not full JSONL—if you want CI trends. |
| **RAG-specific metrics** | If you later add labeled “relevant log line IDs,” you can compute hit@k / nDCG in a separate script reading traces. |
| **Export for SFT** | Transform `records.jsonl` → sharegpt / messages JSONL if you ever fine-tune outside Ollama. |

Full **weight** fine-tuning is **out of scope** for this repository unless you add a dedicated training pipeline.

## Autonomous iteration (Cursor / agent chat)

**What exists in-repo:** one-shot **`logpilot eval run`** (suite × repeats → artifacts under `-o`). There is **no** built-in “loop 40 times and edit code” command—that **orchestration is the agent’s job** in the chat.

**Load:** Expect **one Ollama (or API) call per question per repeat** for answers only—no extra judge traffic.

### Canonical prompt for the full loop

Use **[`EVAL_LOOP_PROMPT.md`](EVAL_LOOP_PROMPT.md)** as the single runbook. **Human:** in Cursor, `@docs/agents/EVAL_LOOP_PROMPT.md` and say e.g. “run the eval loop” (optionally: rounds, HTTP vs in-process, `--max-items`). The file is self-contained; link here and [`eval/README.md`](../../eval/README.md) for extra detail.

If you cannot attach files, say: *Follow `docs/agents/EVAL_LOOP_PROMPT.md` in this repo.*

### Safer variants

- **Human edits only:** Agent runs eval + summarizes; **you** change code; agent only re-runs eval. Lowest risk.
- **Round cap only:** e.g. **5 rounds** first; scale up after you like the trend.
- **Subset suite:** Copy a smaller JSON suite for faster loops, then full `default_questions.json` before merge.

## Maintenance

If you add CLI flags, new artifact files, or change suite schema, update **[`eval/README.md`](../../eval/README.md)**, this file, and the **[`MAINTAIN.md`](MAINTAIN.md)** matrix row for `eval/**`.

**Design note:** [006 — Eval records answers; humans/agents judge](../decisions/006_eval_no_llm_judge.md).
