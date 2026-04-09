# Agent documentation index

**Maintenance (read for almost every code change):** **[`MAINTAIN.md`](MAINTAIN.md)** — which docs, env files, migrations, and tests must stay aligned with each kind of edit. Use it as a **checklist before marking work complete**.

Canonical policies for coding agents (any IDE) also live in **[`AGENTS.md`](../../AGENTS.md)** at the repo root. **Cursor-only** hints are under [`.cursor/rules/`](../../.cursor/rules/) and must not duplicate full policy—see those files for summaries + pointers here.

## Start here

| Document                       | Purpose                                                                                     |
| ------------------------------ | ------------------------------------------------------------------------------------------- |
| [`AGENTS.md`](../../AGENTS.md) | **Git:** routine work on **`develop`** only; **`experimental/*`** for risky/major spikes; remotes not prescribed |
| [`MAINTAIN.md`](MAINTAIN.md)   | **Required:** if you change X, update Y (env, README, migrations, tests, decisions)         |

## Product & ops

| Document                                               | Purpose                                        |
| ------------------------------------------------------ | ---------------------------------------------- |
| [`../../README.md`](../../README.md)                   | Humans + setup: architecture, quick start, API |
| [`../ingest-embed-fixes.md`](../ingest-embed-fixes.md) | Ingest/embed design notes                      |
| [`../plans/README.md`](../plans/README.md)              | **Execution plans** (roadmaps, scoped rollouts) |
| [`AUTOMATION.md`](AUTOMATION.md)                       | **Hooks, `make check`, decisions** — agent/contributor automation |
| [`EVAL.md`](EVAL.md)                                   | **Batch eval:** `logpilot eval run`, suites, review rubric, comparing runs |
| [`EVAL_LOOP_PROMPT.md`](EVAL_LOOP_PROMPT.md)           | **Agent @-mention:** eval → rubric review → code fixes → `make check` → repeat |

## Automation (local + CI)

| Entry                                                        | Purpose                                         |
| ------------------------------------------------------------ | ----------------------------------------------- |
| `make check` (see repo [`Makefile`](../../Makefile))         | **Ruff + pytest** — run when validating changes |
| [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) | Same checks on pushes to `main` and `develop`   |

## Decisions (why, not only what)

| Location                         | Purpose                                                                                          |
| -------------------------------- | ------------------------------------------------------------------------------------------------ |
| [`../decisions/`](../decisions/) | Append-only ADR-lite notes; add a file when a design choice should survive across agent sessions |

## Docker

**Cursor agents** must follow [`.cursor/rules/docker-compose-after-changes.mdc`](../../.cursor/rules/docker-compose-after-changes.mdc): mandatory `docker compose` rebuild when **trigger paths** change, a **strict skip allowlist** for doc-only work, and a required **`Docker Compose:`** line in the final reply. **Humans:** use the same commands when you change the app image or Compose behavior.
