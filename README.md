# logpilot

Self-hosted log intelligence for a Linux homelab: ingest **Docker JSON logs** plus common **host text logs** (syslog, auth, `/var/log/*.log`, etc.), store them in PostgreSQL with pgvector embeddings, and ask questions in natural language using a local Ollama LLM. **No cloud APIs.**

**Coding agents:** read [`AGENTS.md`](AGENTS.md), [`docs/agents/MAINTAIN.md`](docs/agents/MAINTAIN.md) (**keep docs/env/tests in sync** — use its matrix whenever you change code), [`docs/agents/AUTOMATION.md`](docs/agents/AUTOMATION.md) (hooks + verification habits), and [`docs/agents/INDEX.md`](docs/agents/INDEX.md) (full index, CI). Run `make check` when validating changes; optional `make install-git-hooks` runs checks on `git push`.

## Architecture

```
  Host                          Docker Compose
+------------------+           +---------------------------+
| Ollama :11434    | <---------|  logpilot (Python)      |
| (ollama serve)   |  HTTP     |    ingest + embed + API |
+------------------+           |          |                |
| /var/lib/docker/ |  (ro)     |          v                |
|   containers/    | --------> |  PostgreSQL 16 + pgvector|
+------------------+           +---------------------------+
```

Data flow:

1. **Ingest** tails `*-json.log` under `DOCKER_LOG_ROOT` (optional **read-only** Docker socket for `docker:<container_name>` sources), optional **`journalctl --follow`** for the systemd journal (cursor in `journal_cursors`), and plain-text files under `/var/log`, tracking file offsets in Postgres for files and a journal cursor for journald.
2. **Embed** fills `embedding` (768-d) via Ollama `nomic-embed-text`, with optional **sentence-transformers** fallback if Ollama is unreachable and the extra is installed.
3. **Query** embeds your question, runs pgvector similarity search over a **time window**, then asks Ollama (`llama3` by default) with retrieved log lines as context.

Stack: Python 3.11+, async SQLAlchemy + **asyncpg**, Alembic, Typer CLI, FastAPI (optional in-process).

### Grounding

Answers are meant to be **evidence-backed**: **retrieved log lines** (embedded in Postgres), optional **read-only host or Docker snippets** when intent enables them (e.g. on-demand `journalctl`, Docker Engine inspect, **`disk_usage`**, **`cpu_thermal`**, **`gpu_status`**), or an explicit **no data / unavailable** message — not plausible filler. The product does **not** expose arbitrary shell to the model; new host capabilities are added as **allowlisted, typed tools** (see [ADR `005`](docs/decisions/005_local_sysadmin_copilot_vision_tools_grounding.md) and the phased plan in [`docs/plans/local-sysadmin-copilot-roadmap.md`](docs/plans/local-sysadmin-copilot-roadmap.md)).

## Prerequisites

- Debian (or similar) with Docker and Docker Compose v2
- **Ollama running on the host** (default setup): models live on the host; no second Ollama container (avoids port **11434** conflicts)
- Enough disk for Ollama models (several GB) and Postgres data
- For GPU acceleration: NVIDIA container toolkit (optional); CPU works but is slower
- Read access to Docker container logs on the host (often root-owned under `/var/lib/docker/containers`)

## Quick start

1. Copy environment file and edit secrets:

   ```bash
   cp .env.example .env
   ```

2. Ensure **Ollama is running on the host** (e.g. `ollama serve` on port 11434).

3. Start Postgres + logpilot:

   ```bash
   docker compose up -d --build
   ```

4. Pull embedding and chat models into **host** Ollama:

   ```bash
   ./scripts/bootstrap.sh
   ```

   This uses the `ollama` CLI on your **host** (`ollama pull …`). If the CLI is not in `PATH`, the script prints API `curl` examples.

5. Migrations run automatically on container start (`alembic upgrade head` in `docker/entrypoint.sh`). Check API health:

   ```bash
   curl -s http://127.0.0.1:8080/health
   ```

### systemd host checklist (embedded journal RAG)

On a host using **systemd**, to get **`journal:…` rows** into Postgres and embeddings (not only on-demand `journalctl`):

1. **Migrations:** On an **existing** database, ensure schema is current **before** relying on `JOURNAL_INGEST=true` — **restart the logpilot container** once (so `docker/entrypoint.sh` runs `alembic upgrade head`) or run `alembic upgrade head` yourself so **`journal_cursors`** exists.
2. **Compose:** Uncomment the **`/var/log/journal`** volume in `docker-compose.yml` (read-only). **`/var/run/docker.sock`** is already mounted by default for Docker log names and live engine inspect — remove that volume and set **`DOCKER_QUERY_ON_DEMAND=false`** only if you want to drop live container state. **`/run/dbus/system_bus_socket`** is mounted by default so **`logpilot ask`** inside the API container can query the **host** systemd over D-Bus: native **`systemctl`** when it works, otherwise read-only **`busctl --system`** for unit **ActiveState** / **SubState** (typical in Docker because **`systemctl`** often rejects non-PID-1 runtimes). Comment the socket out on hosts without that path.
3. **`.env`:** Set **`JOURNAL_INGEST=true`**, **`JOURNAL_DIRECTORY=/var/log/journal`** (path inside the container = mount target). Optionally set **`JOURNAL_MACHINE_ID`** to the host’s `/etc/machine-id` so cursors stay stable if you recreate the container.
4. **Permissions:** The process must **read** the mounted journal (often: add the container user to the host **`systemd-journal`** group, or run as root for homelab). See **Permissions / security notes** below.
5. **Verify:** After ingest and embed have run, use **`logpilot doctor`** (add **`--verbose`** for 24h row counts and pending embeddings).

## CLI (host or `docker compose exec`)

The `logpilot` command is **not** on your PATH until you install the package once (Quick start only starts Docker):

```bash
python -m venv .venv
source .venv/bin/activate          # fish: source .venv/bin/activate.fish
pip install -e .
```

Then, from the project directory with `.env` loaded:

```bash
logpilot doctor
logpilot doctor --verbose   # journal/docker/file row counts (24h), pending embeddings
logpilot probe disk-usage   # read-only df summary (see roadmap tools layer); add --json for full output
logpilot probe cpu-thermal  # loadavg + sysfs thermal (`cpu_thermal` tool)
logpilot probe gpu-status   # nvidia-smi CSV and/or rocm-smi (`gpu_status` tool)
logpilot ask "What failed in the last hour?"
```

By default one **intent** LLM call infers: search window (e.g. “last **3** days” → `3d`), `top_k`, `source_scope`, optional `min_level` / `source_contains`, and **booleans** for whether to include the ingestion **inventory** preamble, on-demand **`journalctl`** (when no embedded `journal:` rows), **reboot-focused** journal (`--list-boots` / `-g` / `-k`) for **host OS** boots, **Docker Engine** live inspect (`RestartCount`, state) when **`DOCKER_QUERY_ON_DEMAND=true`** (default under Compose + settings) and the socket is available, read-only **`disk_usage`** (`df`) for disk **capacity** / free-space questions — **not** disk I/O load (`iostat`-style) — when **`DISK_USAGE_QUERY_ON_DEMAND=true`** (default), read-only **`cpu_thermal`** (load average + sysfs thermal) when **`CPU_THERMAL_QUERY_ON_DEMAND=true`** (default), read-only **`gpu_status`** (`nvidia-smi` / `rocm-smi`) when **`GPU_STATUS_QUERY_ON_DEMAND=true`** (default), **meta-coverage** labeling, and the **keyword supplement** on retrieval. If you say nothing about time, the model should default to about **1h** and **20** lines over **all** families. Override scalars when needed: `logpilot ask "any nginx errors?" --since 7d --top-k 40 --source-scope docker --min-level err --source-contains nginx`. Use `--raw` to skip the intent LLM (inventory / journal-on-demand / Docker engine / disk / CPU-thermal / GPU probes / keyword supplement default **off**; set `--since` etc. manually). Use `--agent` for bounded multi-step retrieval; on-demand **`journalctl`**, **`disk_usage`**, **`cpu_thermal`**, and **`gpu_status`** still run when intent enables them (same as without `--agent`). Add `--debug` for a JSON trace.

Same commands work as `python -m query.cli doctor` / `python -m query.cli ask ...` after that install.

**Batch evaluation:** `logpilot eval run -o eval/runs/<name>` runs [`eval/suites/default_questions.json`](eval/suites/default_questions.json) once per question by default (fast iteration); add `--repeats 3` for variance. Use in-process when host `.env` matches DB + Ollama, or `--base-url http://127.0.0.1:8080` under Compose (recommended). In-process trials honor **`LOGPILOT_EVAL_INPROCESS_TIMEOUT_S`** (default 180s). Artifacts are for **human or Cursor review** (see [`eval/rubric.md`](eval/rubric.md)); `--max-items N` smoke-runs the first *N* questions. Details: [`eval/README.md`](eval/README.md), [`docs/agents/EVAL.md`](docs/agents/EVAL.md). **Agent improve loop:** [`docs/agents/EVAL_LOOP_PROMPT.md`](docs/agents/EVAL_LOOP_PROMPT.md).

**No host install:** use the app in the container: `docker compose exec logpilot logpilot doctor`

Run the full daemon locally (without Docker) after `pip install -e .` and a reachable Postgres:

```bash
logpilot run
```

## HTTP API

- `GET /health` — liveness
- `POST /query` — JSON body: required `question`; optional `since`, `top_k`, `source_scope` (`all` \| `journal` \| `docker` \| `file`), `min_level`, `source_contains`, `use_intent` (default `true`), `agent` (default `false`, bounded multi-step planner; on-demand `journalctl` / `disk_usage` / `cpu_thermal` / `gpu_status` still apply when intent enables them), `include_answer_prompt` (default `false`; when `true`, response may include `answer_prompt` — the full RAG user message sent to the chat model, large). Query parameter `debug=true` adds a `trace` array when available. When `use_intent` is true, the **intent model** sets the time window (e.g. user asks for three days → `3d`), filters, and the **behavior flags** above (inventory, on-demand `journalctl`, host reboot focus, optional Docker engine inspect, optional disk / CPU-thermal / GPU probes, keyword supplement). Explicit JSON fields override **scalars** only; they do not flip intent booleans. If intent picks a narrow `source_scope` but that family has no embedded lines in the window, retrieval **retries once** with `source_scope=all`. **Retrieval** filters ingested rows; enable `JOURNAL_INGEST` and mounts so `journal` has data.

Example (natural language only):

```bash
curl -s http://127.0.0.1:8080/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"Any errors in the last hour? Summarize broadly."}'
```

Example with explicit overrides:

```bash
curl -s http://127.0.0.1:8080/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"nginx errors","since":"7d","top_k":25}'
```

## Host logs vs Docker-only

logpilot answers from **ingested, embedded rows in Postgres** — not from live `journalctl` or arbitrary host paths unless they are wired in. Default Compose mounts **Docker container JSON logs** and **`HOST_LOG_ROOT` → `/var/log`** for plain-text files, but **`JOURNAL_INGEST` defaults to `false`**, so **systemd journal lines** are often **not embedded** as `journal:…` rows until you enable continuous ingest and wait for embedding.

**On-demand journal (default on at the app level):** when the **intent model** sets `journalctl_on_demand` and there are **no** embedded `journal:` rows, the query path runs **`journalctl`** against the mounted journal directory (`JOURNAL_DIRECTORY` or `/var/log/journal`) and appends that text — **no embedding required**. If **`reboot_journal_focus`** is true, the path prefers **`journalctl --list-boots`**, then **`journalctl -g`**, then **`journalctl -k`**, not a full unfiltered tail. The host journal must be **readable** in the container (see Permissions). Set **`JOURNAL_QUERY_ON_DEMAND=false`** to disable.

When the intent model sets **`include_inventory_context`**, the prompt includes the **inventory preamble** (env flags + embedded row counts). For **continuous** journal RAG over history, enable **`JOURNAL_INGEST=true`** and let the embed worker fill `journal:` rows.

**Docker Engine on demand (answers):** default **`DOCKER_QUERY_ON_DEMAND=true`**. **Docker Compose** mounts **`/var/run/docker.sock`** read-only and sets the flag explicitly (override in `.env` to opt out). When the intent model sets **`docker_engine_on_demand`**, `logpilot ask` appends a read-only **inspect table** (`RestartCount`, state, `StartedAt`) from **`GET /containers/json`** and **`GET /containers/{id}/json`**. **`RestartCount` is cumulative since container creation**, not “restarts today” unless you treat it that way explicitly; time-window restart counts would need **`docker events`** (not built in yet).

**Disk usage on demand (answers):** default **`DISK_USAGE_QUERY_ON_DEMAND=true`**. When the intent model sets **`disk_usage_on_demand`**, `logpilot ask` runs the allowlisted **`disk_usage`** tool (`df -B1 -P`) and appends a short summary + table to the prompt — **used/free/% full only**, not throughput or “disk busy.” Values reflect **this environment’s mount namespace** (container vs host); bind-mount host paths read-only if you need the host’s view.

**CPU / thermal on demand (answers):** default **`CPU_THERMAL_QUERY_ON_DEMAND=true`**. When the intent model sets **`cpu_thermal_on_demand`**, `logpilot ask` runs **`cpu_thermal`** (`/proc/loadavg` + `/sys/class/thermal/thermal_zone*`). Many containers/VMs have **load** but **no** thermal zones — say so honestly; do not invent temperatures.

**GPU status on demand (answers):** default **`GPU_STATUS_QUERY_ON_DEMAND=true`**. When the intent model sets **`gpu_status_on_demand`**, `logpilot ask` runs **`gpu_status`**: fixed **`nvidia-smi`** CSV first, then **`rocm-smi`** if NVIDIA did not return usable data. The default **logpilot** image does **not** ship GPU tools — use a host install, a custom image, or **NVIDIA Container Toolkit** as appropriate; when binaries are missing, the probe reports failure and the model must **not** invent VRAM or GPU temperatures.

**Host services on demand (answers):** default **`HOST_SERVICES_QUERY_ON_DEMAND=true`**. For service-status style questions (especially with `source_contains` like `samba`, `sshd`, `nginx`), `logpilot ask` can append a read-only **`systemctl`** snapshot (`list-units` + `status <unit>` candidates). This gives live native-service state even when no matching embedded rows exist in the current window.

### `parsed` service hints (optional)

Ingest may set **`parsed.service_key`** and **`parsed.service_label`** on rows (additive JSONB, no migration). Conventions:

- **Journal:** e.g. `unit:nginx.service`, `syslog_id:sshd`, `comm:ollama` (only when that metadata exists; no placeholder like `journal:unknown` in these fields).
- **Docker:** `docker:<container_name>` or `docker:<short_id>` when the name is unknown.
- **Plain-text `file:` sources:** not populated in v1 (syslog tag parsing deferred).

RAG context lines include **`service_key`** when present so the answer model can refer to a stable service id.

## Configuration

All configuration is via environment (see `.env.example`):

- **`DATABASE_URL`** — async URL, e.g. `postgresql+asyncpg://...`
- **`OLLAMA_BASE_URL`** — use **`http://127.0.0.1:11434`** in `.env` for **host** CLIs (`logpilot ask`, in-process eval). The **logpilot** Compose service **overrides** this to `http://host.docker.internal:11434` so the container reaches Ollama on the host (`extra_hosts: host-gateway`).
- **`DOCKER_LOG_ROOT`** — host path mounted read-only for container JSON logs
- **`HOST_LOG_ROOT`** — host directory mounted read-only at `/var/log` in the container (default `/var/log` on the host) for syslog-style files
- **`TEXT_LOG_INGEST`** — set `false` to disable plain-text host log ingestion
- **`TEXT_LOG_PATHS`** — comma-separated paths or globs; empty uses built-in defaults under `/var/log`. Ingests **text** files only. With **`JOURNAL_INGEST=true`**, the defaults **exclude** `/var/log/syslog` and `/var/log/messages` (common rsyslog duplicates); set **`TEXT_LOG_INCLUDE_JOURNAL_DUPLICATE_PATHS=true`** to force them back.
- **`JOURNAL_INGEST`** — set `true` to run `journalctl --follow --output=json` (needs `journalctl` in the image and access to journal files; in Docker set **`JOURNAL_DIRECTORY=/var/log/journal`** and mount the host directory read-only — see `docker-compose.yml` comments).
- **`JOURNAL_QUERY_ON_DEMAND`** — default `true`; for host-level questions, run a one-shot `journalctl` when embedded `journal:` rows are zero (see **Host logs vs Docker-only** above).
- **`JOURNAL_DIRECTORY`**, **`JOURNAL_MACHINE_ID`**, **`JOURNAL_FLUSH_BATCH_SIZE`** — journal path (e.g. mounted host journal), optional stable cursor key, batch size for DB writes.
- **`DOCKER_ENRICH_CONTAINER_NAMES`**, **`DOCKER_SOCKET_PATH`** — when the socket is mounted **read-only**, map container IDs to names via `GET /containers/json`; disable enrichment if you prefer raw `docker:<id>` sources (socket may still be mounted for live inspect).
- **`DOCKER_QUERY_ON_DEMAND`** — allow Docker Engine live inspect in answers when intent requests it (default **`true`**; Compose wires this with the socket mount — set **`false`** to disable).
- **`DISK_USAGE_QUERY_ON_DEMAND`** — allow read-only **`disk_usage`** / `df` in answers when intent requests it (default `true`; set `false` to disable).
- **`CPU_THERMAL_QUERY_ON_DEMAND`** — allow read-only **`cpu_thermal`** in answers when intent requests it (default `true`; set `false` to disable).
- **`GPU_STATUS_QUERY_ON_DEMAND`** — allow read-only **`gpu_status`** (`nvidia-smi` / `rocm-smi`) in answers when intent requests it (default `true`; set `false` to disable).
- **`HOST_SERVICES_QUERY_ON_DEMAND`** — allow read-only **`systemctl`** snapshots for native service-status questions (default `true`; set `false` to disable).
- **`EMBED_BATCH_SIZE`**, **`EMBED_POLL_INTERVAL_S`**, **`INGEST_POLL_INTERVAL_S`** — ingest/embed worker tuning
- **`USE_EMBEDDING_FALLBACK`** — set `true` to prefer sentence-transformers for embeddings
- **`ST_EMBEDDING_MODEL`** — Hugging Face model id when using the ST fallback
- **Query / agent (optional):** `QUERY_AGENT_MAX_STEPS`, `QUERY_AGENT_MAX_TOTAL_ROWS`, `QUERY_AGENT_TIMEOUT_S` bound the planner when `agent=true`; `QUERY_ANSWER_TIMEOUT_S` limits the final answer LLM (`0` = default client timeout); `QUERY_CONTEXT_REDACT_REGEX` optionally strips patterns from log context before the answer model.

**`logpilot doctor`** checks DB, Ollama, Docker log root, **`JOURNAL_INGEST`** / **`journalctl`** / **`JOURNAL_DIRECTORY`**, Docker socket enrichment, and (with **`--verbose`**) last-24h row counts by source family plus pending embeddings. It distinguishes **embedded journal RAG** from **on-demand `journalctl`**.

Compose defines a healthcheck for **logpilot** (`GET /health` via `curl` inside the app image). **Ollama is not part of Compose** by default so port **11434** stays with your existing `ollama serve` on the host.

## Troubleshooting: no `journal:` rows

1. **`JOURNAL_INGEST=false`** — turn it on in `.env` and restart; continuous ingest is off by default.
2. **No journal mount** — uncomment **`/var/log/journal`** in `docker-compose.yml` and set **`JOURNAL_DIRECTORY=/var/log/journal`**.
3. **Permissions** — container cannot read the host journal; fix **`systemd-journal`** group / ACLs (see below).
4. **Embed lag** — new lines appear in `logs` first; **`embedding`** fills asynchronously; **`logpilot doctor --verbose`** shows pending embed count.
5. **Fresh database** — only recent activity: doctor avoids a false “journal empty” warning until older rows exist (see verbose stats).

**On-demand `journalctl`** can still answer some questions without embedded rows; it does **not** replace ingest + embed for historical RAG.

## Permissions / security notes

- Container logs are often readable only as root on the host. Common options: run the `logpilot` container as root (simplest for homelab), or adjust host permissions/ACLs carefully.
- **Journal:** reading `/var/log/journal` may require matching host permissions or running the container as a user in the host’s `systemd-journal` group (see `group_add` in Compose if you refine this).
- **Docker socket:** mounting **`/var/run/docker.sock` (even read-only)** materially expands attack surface (the Engine API is powerful). The app uses only **`GET /containers/json`** and **`GET /containers/{id}/json`** for names + live inspect. To run without it: remove the socket volume from **`docker-compose.yml`**, set **`DOCKER_QUERY_ON_DEMAND=false`**, and set **`DOCKER_ENRICH_CONTAINER_NAMES=false`** if you want `docker:<short-id>` sources only.
- **systemd D-Bus:** mounting **`/run/dbus/system_bus_socket`** lets processes in the container talk to the host **system** bus (what **`systemctl`** uses for unit status). That is broader than a single read-only file: treat it like the Docker socket—homelab convenience with real trust boundaries. Remove that volume if you only want host-side **`logpilot ask`** for **`systemctl`**.
- Change default Postgres password in `.env` before exposing ports beyond localhost.

## Example questions

- `logpilot ask "What failed in the last hour?" --since 1h`
- `logpilot ask "Show stack traces from the last day" --since 24h --top-k 40`
- After Pi-hole ingestion exists: `logpilot ask "Which domains were blocked today?" --since 12h`

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"                 # ruff + pytest; add ".[embeddings-local]" if needed
alembic upgrade head
make check                              # ruff + pytest; use PYTHON=.venv/bin/python if make picks wrong python
make install-git-hooks                  # optional: pre-push runs make check (skip: LOGPILOT_SKIP_HOOKS=1 git push)
```

CI runs the same checks on **GitHub Actions** for `main` and `develop` (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)). Product direction and phased roadmap: [`docs/plans/local-sysadmin-copilot-roadmap.md`](docs/plans/local-sysadmin-copilot-roadmap.md).
