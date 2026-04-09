# Automation for agents and contributors

**Goal:** Encode repetitive quality steps so **humans and coding agents** do not skip them by accident.

## Mandatory checklist (substantive code)

1. **`docs/agents/MAINTAIN.md`** — if your change matches a row in the matrix, update the listed artifacts in the **same** task.
2. **`make check`** — run before considering work complete (generated `docs/plans` index, `ruff`, `pytest`). With a venv: `PYTHON=.venv/bin/python make check`.
3. **Cross-cutting design** — add or update a file under **`docs/decisions/`** (see template in [`../decisions/README.md`](../decisions/README.md)) so the choice is not re-debated in later sessions.
4. **Directional / phased work** — if you change roadmap scope or sequencing, update **[`../plans/local-sysadmin-copilot-roadmap.md`](../plans/local-sysadmin-copilot-roadmap.md)** (or the relevant plan under [`../plans/`](../plans/)). When you add, drop, or retitle an indexed plan, run **`make plans-index`** (or **`make check`**, which verifies the index).

## Git hooks (optional, recommended)

Install **once per clone** so **`git push`** runs the same checks as CI:

```bash
make install-git-hooks
```

This sets `core.hooksPath` to **`.githooks`** and runs **`make check`** on **pre-push**. If **`PYTHON`** is unset and **`.venv/bin/python`** exists, the hook uses that interpreter (typical after `python -m venv .venv` + `pip install -e ".[dev]"`).

To skip temporarily (emergency push—use sparingly):

```bash
LOGPILOT_SKIP_HOOKS=1 git push
```

Hooks require **`make`**, **Python 3.11+**, and dev deps (`pip install -e ".[dev]"`).

## CI

GitHub Actions runs **`ruff`** and **`pytest`** on pushes and PRs to **`main`** and **`develop`** (see [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)). Hooks are a **local** complement; they do not replace CI.

## Cursor / IDE agents

- Root **[`AGENTS.md`](../../AGENTS.md)** and **[`MAINTAIN.md`](MAINTAIN.md)** are the canonical policies.
- **[`.cursor/rules/agent-automation.mdc`](../../.cursor/rules/agent-automation.mdc)** reminds Cursor agents to run checks, log decisions, and keep tasks small.
- After Docker image–affecting changes, follow **[`.cursor/rules/docker-compose-after-changes.mdc`](../../.cursor/rules/docker-compose-after-changes.mdc)**.

## Small tasks

Prefer **one focused change** (one concern per PR/commit series): easier review, cleaner `MAINTAIN` updates, and fewer merge conflicts for automated runs.
