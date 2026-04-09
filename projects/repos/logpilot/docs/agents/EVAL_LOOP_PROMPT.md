# Eval improvement loop — agent runbook

**Human:** Point your agent at this file (e.g. `@docs/agents/EVAL_LOOP_PROMPT.md`) and say **run the eval loop**. Optionally add: number of rounds, `--max-items N` for smoke, in-process vs HTTP (`http://127.0.0.1:8080`), or “do not edit the suite.”

**Agent:** Execute the loop below from the **repository root**. Deep reference (flags, artifacts, comparing runs): `[EVAL.md](EVAL.md)` and `[eval/README.md](../../eval/README.md)`.

---

## Defaults (use if the human did not specify)


| Choice               | Default                                                                                                                                                                                                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Git branch           | `develop` (see `[AGENTS.md](../../AGENTS.md)`)                                                                                                                                                                    |
| Rounds               | **3**, or until the human says **STOP** (whichever comes first). Prefer **more, shorter** rounds (default **1** repeat per question) over fewer rounds with **3×** repeats—same suite diversity, faster feedback. |
| Repeats per question | **1** (default CLI). Use **`--repeats 3`** only when you need variance / flake signal (e.g. pre-merge).                                                                                                            |
| Suite                | `eval/suites/default_questions.json` — **do not edit** unless the human explicitly allows (suite aims for **cross-topic** coverage: hardware probes, systemd/Docker/journal/file scopes, reboots, and odd phrasing)                                                                                                                         |
| Mode                 | **HTTP** to `http://127.0.0.1:8080` when the API is up (typical Compose) — avoids host-vs-container DB/Ollama mismatches. **In-process** only if `logpilot ask` works on the host with the same `.env`; trials are capped by `LOGPILOT_EVAL_INPROCESS_TIMEOUT_S` (default 180s) so runs do not stall forever. If neither works, **stop and report**. |
| Smoke                | Full suite. If the human asked for a quick run, add `--max-items 10` (or the number they gave).                                                                                                                   |
| Traces               | Omit `--debug` unless you need retrieval traces in `records.jsonl` to diagnose a prior round.                                                                                                                     |


Do **not** wait unbounded on eval: if `records.jsonl` stays empty past ~2× the per-trial timeout, treat the run as stuck, stop it, and switch mode or fix connectivity. Prefer **HTTP** when `curl -sf http://127.0.0.1:8080/health` succeeds.

Ask **one short clarifying message** only if mode (in-process vs HTTP) or round count is ambiguous **and** you cannot infer from context (e.g. Compose already running, `.env` present).

---

## Before round 1

1. Read `**[eval/rubric.md](../../eval/rubric.md)`** end-to-end. You will use it as a **manual** checklist when reading answers — **do not** send the rubric to Ollama (or any model) as an automated judge.
2. Confirm you are on the branch the human expects (default `**develop`**).

---

## Each round (k = 1, 2, …)

1. **Output directory** — use a **new** path each round, e.g. `eval/runs/loop-YYYYMMDD-HHMM-r<k>` (include time so runs never collide).
2. **Run the eval** from repo root using the project venv’s CLI (same install as `make check`):
  ```bash
   .venv/bin/logpilot eval run -o <output-dir>
  ```
   (Omit extra flags unless the human asked; default is **one** trial per suite item. Add `--repeats 3` for variance runs.)
   Default suite is `eval/suites/default_questions.json` (omit `--suite` unless the human named another file).
   - **HTTP / Compose (default when API is healthy):** append `--base-url http://127.0.0.1:8080`.
  - **Traces in JSONL:** add `--debug`.
  - **Smoke:** add `--max-items N`.
   If `.venv/bin/logpilot` is missing, install the package in a venv first (e.g. `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` per `[README.md](../../README.md)`), then retry.
3. **Review artifacts** in `<output-dir>` (**you are the rubric judge** — read Q vs A in natural language; the CLI does not auto-score):
  - `summary.json` — errors per `item_id`, latency means/maxes.
  - `records.jsonl` — for failing or weak `item_id`s, read `question`, `answer`, `error`, and `trace` (if present). Apply `**eval/rubric.md`** dimensions (groundedness, humility, relevance, safety). Say explicitly what is wrong before changing code.
4. **Improve the product** with **minimal, focused** code changes (`query/`, `logpilot/`, `ingestor/`, `embedder/`, `db/`, etc.). Do **not** change the suite JSON or the rubric unless the human explicitly allowed it.
5. **Verify:**
  ```bash
   PYTHON=.venv/bin/python make check
  ```
   Fix until green.
6. **Docker:** If you changed any file under the repo’s Docker rebuild triggers (see `[.cursor/rules/docker-compose-after-changes.mdc](../../.cursor/rules/docker-compose-after-changes.mdc)` / `[INDEX.md](INDEX.md)`), run from repo root:
  ```bash
   docker compose down && docker compose up -d --build --remove-orphans
  ```
   Wait until services are healthy when applicable. If the eval uses **HTTP**, the rebuilt API must match your changes.
7. **Report briefly** to the human: what you changed, and how this round compares to the last (errors, obvious answer quality, latency if notable).

Then increment `k` and start the next round unless a stop condition fired.

---

## Stop conditions

- The human says **STOP**, or  
- You completed the agreed number of rounds, or  
- **Blocker:** DB unreachable, Ollama down, API not responding, `make check` cannot be fixed in reasonable time — report clearly and stop.

---

## Constraints

- Small, reviewable diffs; no unrelated refactors.  
- No force-push; remote Git operations are the human’s unless they said otherwise.  
- **Do not** add batch scoring inside `logpilot eval` by calling the **same** Ollama `CHAT_MODEL` that produced the answers ([`006_eval_no_llm_judge.md`](../decisions/006_eval_no_llm_judge.md)). **You** (the agent) applying the rubric while reading JSONL is the intended judge.

---

## Optional variants (only if the human asks)

- **Human edits code:** You only run eval + summarize; the human applies patches; you re-run eval.  
- **Subset suite:** Use a smaller copied JSON suite for speed, then full `default_questions.json` before merge.

