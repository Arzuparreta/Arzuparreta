# Documentation and artifact triggers

**Agents:** This file is a **mandatory checklist**, not background reading. When your change matches a row below, **update the listed artifacts in the same task**. Leaving `.env.example`, README, migrations, or decisions stale is a failed change.

When you change the codebase, update the related artifacts so the next agent (or human) does not rely on stale docs or broken env examples.

## Matrix (if you change … then update …)

| Change | Update |
|--------|--------|
| New or renamed **environment variable** | [`.env.example`](../../.env.example), [README](../../README.md) configuration section if user-facing |
| **Default** env behavior in [`logpilot/settings.py`](../../logpilot/settings.py) | Same as above |
| **Python dependency** | [`pyproject.toml`](../../pyproject.toml); run `make check` / CI deps still install |
| **DB schema** | Alembic migration under [`alembic/versions/`](../../alembic/versions/), [`db/models.py`](../../db/models.py) |
| **Public API or CLI** | [README](../../README.md) CLI/API sections |
| **Ingest/embed/query behavior** worth remembering | [`docs/ingest-embed-fixes.md`](../ingest-embed-fixes.md) or a short note under [`docs/decisions/`](../decisions/) |
| **Agent policy** (branches, Docker, CI) | [`AGENTS.md`](../../AGENTS.md) and/or [`docs/agents/`](./); keep [`.cursor/rules/`](../../.cursor/rules/) as short pointers only |
| **`query/since_parse.py` or `query/intent.py`** | Extend or adjust [`tests/`](../../tests/) so **`make check`** stays green |
| **Cross-cutting design choice** | New file in [`docs/decisions/`](../decisions/) (see template there) |
| **Roadmap / phased plan text**, or **add/remove/rename/archive** a plan under [`docs/plans/`](../plans/) | Edit the relevant `.md` (YAML frontmatter: `plan_index`, `focus` when indexed); use [`docs/plans/archive/`](../plans/archive/) for retired files when links should stay valid; run **`make plans-index`** or **`make check`** so [`docs/plans/README.md`](../plans/README.md) stays in sync |
| **New read-only host / tool connector** (Phase B probes) | Document **required read-only bind mounts** and runtime assumptions here or in README / `.env.example` / Compose comments as appropriate (see [`docs/plans/local-sysadmin-copilot-roadmap.md`](../plans/local-sysadmin-copilot-roadmap.md) §3.4) |
| **Git hook behavior** (`.githooks/`, `scripts/git-hooks/`) | [`docs/agents/AUTOMATION.md`](AUTOMATION.md), [README](../../README.md) Development section |
| **`eval/**` harness** (CLI, suite schema, artifact shape, runner) | [`eval/README.md`](../../eval/README.md), [`docs/agents/EVAL.md`](EVAL.md), [`docs/agents/EVAL_LOOP_PROMPT.md`](EVAL_LOOP_PROMPT.md), [README](../../README.md) eval / CLI section if user-facing |

## Verification

- Run **`make check`** (ruff + pytest) before considering work complete unless the user says otherwise. With a venv, use `PYTHON=.venv/bin/python make check` if the default `python3` is not the venv. Optionally run **`make install-git-hooks`** so **`git push`** runs the same checks (see [`AUTOMATION.md`](AUTOMATION.md)).
- After Docker image–affecting changes, rebuild Compose per [`.cursor/rules/docker-compose-after-changes.mdc`](../../.cursor/rules/docker-compose-after-changes.mdc).

## Where this is linked

Entry points so this stays visible: **[`AGENTS.md`](../../AGENTS.md)** (root), **[`docs/agents/INDEX.md`](INDEX.md)**, **[`README.md`](../../README.md)** (coding agents line), and **`.cursor/rules/docs-and-artifacts.mdc`** (Cursor always-apply summary).
