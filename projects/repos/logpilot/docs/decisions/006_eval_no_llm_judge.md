# 006 — Eval records answers; humans/agents judge (no LLM-as-judge)

## Status

Accepted

## Context

The batch eval harness previously supported `--judge`, which called the same Ollama chat model (`CHAT_MODEL`) to score answers from a markdown rubric. That couples quality signal to a weak or identical model and is a poor substitute for deliberate review.

## Decision

- **Remove** automated LLM judging from `logpilot eval run`.
- The harness **only** runs the suite, repeats trials, and writes `manifest.json`, `records.jsonl`, and `summary.json` (latency and errors).
- **Review** uses `eval/rubric.md` as a human/agent checklist while reading `records.jsonl` (and optional `--debug` traces). Iteration (change code → re-run eval) stays **outside** the CLI, typically in Cursor or manual workflow.

## Consequences

- No extra Ollama traffic per trial for scoring.
- `records.jsonl` no longer includes a `scores` field.
- `summary.json` no longer includes `judge_overall_*` fields.
