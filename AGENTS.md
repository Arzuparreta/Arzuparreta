# Agent instructions

**Keep artifacts in sync:** Before you finish any task that changes behavior, configuration, dependencies, schema, or public surfaces, read **[`docs/agents/MAINTAIN.md`](docs/agents/MAINTAIN.md)** and apply its **if you change X → update Y** matrix (`.env.example`, README, migrations, tests, decisions, etc.). Treat that file as a **required checklist**, not optional context.

**Full agent index:** [`docs/agents/INDEX.md`](docs/agents/INDEX.md) (MAINTAIN, CI, decisions). **Automation (hooks, checks):** [`docs/agents/AUTOMATION.md`](docs/agents/AUTOMATION.md).

---

## Git branches

This repository uses a **three-branch workflow**. Use the branch roles below when deciding **where to implement** changes.

**Remote Git operations** (push, merge, pull requests, force-push, etc.) are **not** specified here—follow your environment (e.g. Cursor) or the user.

**IDE vs this repo:** Some tools suggest creating a branch (e.g. a `cursor/…` name) when you commit. That is a **product default**, not a logpilot rule. For **normal** work, commit **directly on `develop`**—do not create a side branch because the IDE offered one.

## Branch roles

| Branch | Role |
|--------|------|
| **`main`** | Release line: what is considered **shipped / trusted**. **Do not** use it for day-to-day implementation work. |
| **`develop`** | **Where all routine work lands:** fixes, features, docs, refactors. **Commit on this branch**—do **not** create `feature/*`, `fix/*`, or other short-lived branches for typical changes. |
| **`experimental/*`** | Use only when work is **experimental**, **risky**, or **super major** (large or long-running parallel effort that should not block `develop`). Branch from **up-to-date `develop`**, e.g. `experimental/rag-v2`. Prefer a **descriptive prefix**; avoid a single ambiguous branch name `experimental` unless the team explicitly shares one. |

## Where to work

- **Normal change:** check out **`develop`** and implement **on `develop`**. No new branch.
- **Experimental / risky / super major:** create **`experimental/<short-name>`** from **`develop`**, then merge back when ready (per your remote/PR process).
- **Do not** base routine implementation on **`main`**.

## Default assumption

If the user does not specify a branch: **use `develop` directly**. Do **not** assume a `feature/*`, `fix/*`, `cursor/*`, or `experimental/*` branch unless the user (or this policy’s exception) calls for it.

## History and agent traceability

**Goal:** Future readers (humans and coding agents) should see **what changed, when, and in what order**, without relying on a flattened or rewritten history.

- On **`develop`**, prefer **ordinary commits**—one focused commit per logical change when practical, with **clear messages**. Avoid squashing away intermediate steps on the branch where work happens unless the user explicitly wants a squash.
- When bringing **`develop` into `main`**, prefer a **merge commit** so the integration is explicit: e.g. `git checkout main && git merge --no-ff develop` (then push). That records a **single merge node** tied to `develop`’s tip while **keeping every commit** on `develop` reachable in history.
- A **fast-forward** merge of `main` to `develop`’s tip moves `main`’s pointer but **does not** create a merge commit; that is fine for a linear story but **loses** an explicit “released from develop at this point” marker. Prefer **`--no-ff`** when updating `main` if you want that marker for agents and release archaeology.
- **Squash-merge** (or rebase + force-push) onto **`main`** collapses many commits into one: good for a minimal log on `main`, **bad** if you need each step preserved for bisect or agent audit—avoid for `main` unless the user asks.

## Related

- **Doc and artifact triggers:** [`docs/agents/MAINTAIN.md`](docs/agents/MAINTAIN.md) (same as the opening checklist above).
- Docker rebuild after substantive app changes: [`.cursor/rules/docker-compose-after-changes.mdc`](.cursor/rules/docker-compose-after-changes.mdc) (Cursor summary); same command is linked from [`docs/agents/INDEX.md`](docs/agents/INDEX.md).
