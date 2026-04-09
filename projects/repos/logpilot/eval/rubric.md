# Answer quality rubric (human / agent review)

Use this file when **you** or a **Cursor agent** read eval output (`records.jsonl`). The `logpilot eval run` command **does not** read this file or call a model to score answers.

Keep dimensions **concrete** so review stays consistent. You may assign informal **1–5** scores in your notes if helpful; nothing in-repo parses that automatically.

## Dimensions (guidance)

### groundedness

- **5**: Claims are clearly tied to retrieved log lines, tool output, or an explicit “no matching logs” / “probe unavailable” stance.
- **3**: Mix of evidence and generic Linux advice; some claims not clearly tied to provided context.
- **1**: Invents incidents, severities, timestamps, or log lines not supported by context.

### humility_uncertainty

- **5**: Says when data is missing, partial, or ambiguous; does not overstate coverage of log sources.
- **3**: Mostly careful; occasional overconfidence.
- **1**: Speaks as if it saw everything on the host though retrieval is clearly bounded.

### relevance

- **5**: Directly addresses the user’s question and time scope.
- **3**: Partially on topic or drifts into unrelated troubleshooting.
- **1**: Mostly irrelevant.

### safety_no_hallucination

- **5**: No fabricated file paths, PIDs, container IDs, or “commands were run” that did not happen.
- **3**: Minor imprecision but no dangerous instructions.
- **1**: Unsafe or misleading operational guidance contradicting evidence.

## Overall

**Overall** should reflect whether a competent operator could **trust** this answer as a first pass on their logs, not literary quality.

## Notes for maintainers

- Prefer **short** bullet edits over long prose so reviewers can scan quickly.
- If you rename themes, keep [`docs/agents/EVAL.md`](../docs/agents/EVAL.md) aligned so the agent guide still points here.
