---
plan_index: true
focus: "Journal ingest UX, `logpilot doctor`, optional `parsed` service identity"
status: draft
---

# Plan: Journal host visibility, doctor diagnostics, and service fields in `parsed`

**Status:** Draft — for review (Claude code reviewer + product).  
**Goal:** Make a typical Linux homelab host **legible** to logpilot end-to-end: continuous **journal ingestion** is easy to turn on correctly, `**logpilot doctor`** surfaces misconfiguration before users blame “the AI,” and `**Log.parsed`** carries **optional, consistent service identity** hints for retrieval and answers—without requiring a new DB migration for JSONB shape (keys are additive inside existing `JSONB`).

**Related:**

- Long-term product direction (sysadmin copilot, tools layer): `[local-sysadmin-copilot-roadmap.md](local-sysadmin-copilot-roadmap.md)` (this plan narrows to **operator UX + `parsed` conventions**).
- Journal subprocess and cursors: `[../decisions/001_journal_subprocess_and_cursors.md](../decisions/001_journal_subprocess_and_cursors.md)`.
- Agent maintenance matrix when implementing: `[../agents/MAINTAIN.md](../agents/MAINTAIN.md)`.

---

## 1. Current state (as-is, accurate to tree)

### 1.1 Journal continuous ingest

- Implemented: `ingestor/journal.py` runs `journalctl --follow --output=json`, persists `__CURSOR__` in `journal_cursors`, batches flushes to `logs`.
- **Off by default:** `JOURNAL_INGEST=false` in settings (see `logpilot/settings.py`, `.env.example`).
- **Docker Compose:** host journal mount and Docker socket are **commented** in `docker-compose.yml`; operators must uncomment and set `JOURNAL_DIRECTORY=/var/log/journal` (or equivalent) in `.env`.
- **Plain-text dedup:** when `JOURNAL_INGEST=true`, default file paths omit `/var/log/syslog` and `/var/log/messages` unless `TEXT_LOG_INCLUDE_JOURNAL_DUPLICATE_PATHS=true`.

### 1.2 `parsed` today


| Source family   | `Log.source` (typical) | Notable `parsed` keys today |
| --------------- | ---------------------- | --------------------------- |
| Journal         | `journal:<unit         | id                          |
| Docker JSON     | `docker:<name          | id>`                        |
| Plain-text file | `file:<path>`          | `logfile` only              |


There is **no single cross-family key** (e.g. `service_key`) for prompts, filters, or future UI. Journal entries already expose structured metadata in `parsed`; Docker exposes container identity; **file lines do not** extract syslog tags or program names yet.

### 1.3 `logpilot doctor`

- Implemented in `query/doctor.py`: DB connectivity, Ollama `/api/tags`, Docker log root directory presence.
- **Journal / ingest signals:** reports **`JOURNAL_INGEST`** on/off; **`journalctl`** on `PATH`; **`JOURNAL_DIRECTORY`** directory existence and read access (or notes when empty and **`/var/log/journal`** exists); optional read-only **`journalctl -n 0`** probe when ingest is on and `journalctl` exists; distinguishes **embedded journal RAG** vs **on-demand `journalctl`** in copy.
- **Docker:** when **`DOCKER_ENRICH_CONTAINER_NAMES`** is on, checks whether **`DOCKER_SOCKET_PATH`** is a socket (INFO when not — names fall back to short IDs).
- **`--verbose`:** async DB stats — row counts in the last **24h** by coarse family (`journal:`, `docker:`, `file:`), count of rows with **`embedding IS NULL` and not `embedding_failed`** (pending embed), and a **conditional WARN** when journal ingest is on, journal files look readable, there are **no** `journal:` rows in that 24h window, but **older** log rows exist (avoids noisy warnings on a totally fresh DB).

### 1.4 On-demand `journalctl` (query path)

- Separate from continuous ingest: when embedded `journal:` rows are absent, query can run one-shot `journalctl` (`JOURNAL_QUERY_ON_DEMAND`, default on). This **does not** replace continuous ingest for **historical RAG** over embedded journal lines. Docs should keep that distinction obvious (README already mentions it; doctor can reinforce it).

---

## 2. Problem statement

1. **Operators enable the wrong combination** — e.g. `JOURNAL_INGEST=true` without mounting host journal, or mount without `JOURNAL_DIRECTORY`, leading to silent failure or confusing logs.
2. **Doctor gives a false “all OK”** when journal-dependent workflows will still return empty retrieval for `source_scope=journal`.
3. **Answers and future filters** cannot lean on a **stable, documented convention** for “what service is this?” across journal vs Docker vs file.

---

## 3. Scope

### In scope

- **Documentation and Compose comments** so the “happy path” for systemd hosts is copy-pasteable and explains permissions (group `systemd-journal`, read-only mounts).
- `**logpilot doctor` extensions** (non-destructive checks; optional read-only `journalctl` probe when ingest is enabled or when journal directory is configured).
- **Optional `parsed` fields** populated at ingest time (no new columns): a small **documented schema** plus implementation in ingestors where data is already available or cheap to add.

### Explicitly out of scope

- **Default `JOURNAL_INGEST`:** remains `false`; improve docs and doctor only. **No** Compose `journal` profile in this plan (nice-to-have later; adds complexity for little gain now).
- **Podman** paths, **Pi-hole** ingestor wiring, **log profiles** (`LOG_PROFILE=debian|…`) — remain deferred per linux-wide plan.
- **NL→SQL** or arbitrary new query API dimensions; any new **indexed** columns for service identity (would need migration + MAINTAIN triggers).
- **Backfill** of `parsed` for existing rows: **forward-only** — no requirement to update historical rows.

---

## 4. Workstream A — Journal “sees my host” (operator path)

**Objective:** Minimize misconfiguration; not necessarily change defaults.


| Item | Action                                                                                                                                                                                                                                                                                                                                                                                                  |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A1   | **README** — Short “systemd host checklist”: on an **existing** deploy, **run `alembic upgrade head`** (or **restart the logpilot container** so `docker/entrypoint.sh` runs migrations) **before** relying on `JOURNAL_INGEST=true`, so `journal_cursors` exists; then uncomment journal volume + `JOURNAL_DIRECTORY`, set `JOURNAL_INGEST=true`, note `journalctl` inside image, link to permissions. |
| A2   | **docker-compose.yml** — Keep mounts commented for safety but add **one consolidated comment block** (numbered steps) matching `.env.example` variable names.                                                                                                                                                                                                                                           |
| A3   | `**.env.example`** — Ensure journal block lists `JOURNAL_INGEST`, `JOURNAL_DIRECTORY`, `JOURNAL_MACHINE_ID`, and one-line pointer to “mount host `/var/log/journal` read-only.”                                                                                                                                                                                                                         |
| A4   | **Optional:** `docs/` troubleshooting subsection — “No journal rows” decision tree: ingest off vs mount vs permissions vs embed lag.                                                                                                                                                                                                                                                                    |


**Exit criteria:** A new operator can follow docs only and get embedded `journal:` rows within one compose cycle, or understand exactly what is missing — including that **schema/migrations** must be current before enabling journal ingest on an existing database.

---

## 5. Workstream B — `logpilot doctor`

**Objective:** Surface configuration and environment issues that affect **ingestion**, not only DB/Ollama.

Proposed checks (all **read-only**; no writes except existing DB ping):


| Check | Condition                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              | Message level                                                                                                                            |
| ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| B1    | `JOURNAL_INGEST=true`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Report ON; else report OFF (informational).                                                                                              |
| B2    | `journalctl` on `PATH`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 | WARN if ingest enabled and binary missing.                                                                                               |
| B3    | `JOURNAL_DIRECTORY` set                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | If set, `Path(...).is_dir()` and attempt `os.access(..., R_OK)`; WARN if ingest enabled and not readable.                                |
| B4    | Default journal path                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | If `JOURNAL_DIRECTORY` empty but `/var/log/journal` exists, INFO that default `journalctl` behavior may differ inside container vs host. |
| B5    | Docker socket                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | If `docker_enrich_container_names` and socket path not a socket, INFO (names fall back to IDs).                                          |
| B6    | **Only when `logpilot doctor --verbose`:** run async DB stats — counts of rows in last 24h by coarse family (`source LIKE 'journal:%'`, `docker:%`, `file:%`) and count `WHERE embedding IS NULL AND embedding_failed IS NOT TRUE` (pending embed). **Journal empty WARN (strict):** emit WARN for “ingest on but no journal rows” only if **(a)** journal ingest is enabled and the journal directory looks OK (same heuristic as today), **(b)** journal-family count in the chosen window is 0, **and (c)** the DB has **at least one** `logs` row with `timestamp` older than **10 minutes** (wall-clock relative to doctor run). If the DB is fresh or only has very recent rows, **skip** this WARN so operators are not trained to ignore doctor on first boot. |                                                                                                                                          |


**Implementation notes:**

- Reuse `get_settings()`; keep doctor **fast** by default (no B6 queries unless `--verbose`); use timeouts on any subprocess test if added later.
- Add Typer/CLI flag: `logpilot doctor --verbose` (implementer wires through `query/cli.py` → `run_doctor(verbose=…)`).

**Exit criteria:** Doctor output explains journal vs on-demand query and flags the top two real-world failures: missing mount and unreadable journal directory.

---

## 6. Workstream C — Optional service fields in `parsed`

**Objective:** Add **documented, optional** keys so query/answer prompts (and future code) can cite a stable “service” concept without schema migration.

### 6.1 Proposed convention (additive)

All keys optional; omit if unknown. Use **namespaced** `service_key` values so families do not collide (e.g. a container named `nginx` vs unit `nginx.service`). Prefer stable strings suitable for display and `ILIKE` filters.


| Key              | Meaning                                                                             | Populated by (v1)    |
| ---------------- | ----------------------------------------------------------------------------------- | -------------------- |
| `service_key`    | Single identifier for correlation                                                   | See derivation rules |
| `service_label`  | Human-readable short label for prompts (may equal `service_key` or a prettier form) | Same                 |
| `systemd_unit`   | Already present for journal                                                         | Keep                 |
| `container_name` | Already present for Docker                                                          | Keep                 |


**Namespace examples (normative):** `unit:nginx.service`, `syslog_id:sshd`, `comm:ollama`, `docker:myapp`, `docker:<short_id>` when name missing. **v2 (not v1):** `file_tag:sshd` from syslog tag parsing — **v1 does not populate `service_key` / `service_label` for `file:` sources** (document in README and here; parsing is brittle across distros and journal already covers the same services on typical systemd hosts).

**Derivation rules (v1):**

- **Journal:** If `systemd_unit` is present → `service_key` = `unit:<systemd_unit>`; else if `syslog_identifier` → `syslog_id:<syslog_identifier>`; else if `_COMM` → `comm:<_COMM>`; else **omit `service_key` and `service_label` entirely** (do **not** set `journal:unknown` — it would match `ILIKE` patterns for “journal” and pollute retrieval).
- **Docker:** `service_key` = `docker:<container_name>` if `container_name` in `parsed`, else `docker:<short_id>` from `container_id` prefix (first 12 chars or project convention — match existing ID display).
- **Plain-text file (`file:`):** **v1 — do not set** `service_key` / `service_label`. Defer syslog tag extraction to **v2**.

### 6.2 Query / answer layer

- **Minimal v1:** Document keys in README + inventory preamble text in `query/inventory.py` so the answer model knows `parsed.service_key` may exist for journal and Docker rows, and is **not** populated for `file:` sources in v1.
- **Optional v1.1:** Include `service_key` (when present) in the per-line context string built for the answer LLM (small diff in `query/rag.py` or equivalent—exact file left to implementer).

**Exit criteria:** New ingested rows (journal + docker) populate `service_key` where inputs exist; `**file:` rows** have no `service_key` in v1 per convention; docs and tests match.

---

## 7. Sequencing (suggested)

1. **A (docs/Compose/env)** — Low risk, immediate operator value.
2. **B (doctor)** — Validates A; catches mistakes early.
3. **C (`parsed` + tests + light prompt/inventory)** — Code + MAINTAIN matrix (README, tests).

Parallelization: A and B can overlap; C can follow or overlap B once CLI `--verbose` contract is clear.

---

## 8. Success criteria (overall)

- Operator following README can enable journal ingest and **doctor confirms** journal path + `journalctl` viability when ingest is on.
- Distinguish clearly: **embedded journal RAG** vs **on-demand journalctl** in doctor + docs.
- New logs carry **optional** `service_key` / `service_label` for journal and Docker; `**file:` sources: not populated in v1** (documented in README and plan).
- `make check` green; MAINTAIN artifacts updated for any behavior/env changes.

---

*End of plan.*