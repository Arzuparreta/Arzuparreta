---
plan_index: true
focus: "**Direction:** grounded local ops copilot, tools layer, phased roadmap (logs → probes → orchestration → UI)"
status: active
---

# Plan: Local sysadmin copilot (vision → execution)

**Status:** Active direction (portfolio + homelab).  
**Summary:** Evolve logpilot from **log-centric RAG** into a **grounded, read-only local operations copilot**: the model answers **one focused question at a time** using **evidence** (ingested logs, structured tool output, documented probes)—not invention. **Chat UI, long-lived memory, and write/automation paths** are explicitly **later**; this plan sequences **core infrastructure**, **connectors**, and **orchestration**.

**Related:**

- Vision / constraints (ADR): [`../decisions/005_local_sysadmin_copilot_vision_tools_grounding.md`](../decisions/005_local_sysadmin_copilot_vision_tools_grounding.md)
- Operator legibility (journal, doctor, `parsed`): [`journal-host-visibility-doctor-and-parsed-service-fields.md`](journal-host-visibility-doctor-and-parsed-service-fields.md)
- Agent workflow + hooks: [`../agents/AUTOMATION.md`](../agents/AUTOMATION.md), [`../agents/MAINTAIN.md`](../agents/MAINTAIN.md)

---

## 1. Product framing (north star)

### 1.1 What “success” looks like

- A **sysadmin** (you) asks natural-language questions: **status**, **errors in logs**, **disk space**, **CPU/GPU temperature**, **Docker container health**, **service state**, etc.
- Answers are **informational**, **scoped to the question**, and **grounded**: they cite or implicitly rest on **retrieved log lines**, **tool JSON/text**, or **explicit “no data”**—not plausible filler.
- **All sensitive processing stays local** (aligns with current Ollama + Postgres stack and portfolio narrative).

### 1.2 Non-goals (for this roadmap phase)

- **Arbitrary shell** from the LLM (no “run whatever `bash -c` the model says”). Use **allowlisted tools** with **fixed contracts** instead.
- **Silent writes** to the system (config changes, package install, container start/stop) without a **separate**, explicitly designed safety layer—out of scope until read-path is solid.
- **Full replacement** for metrics stacks (Prometheus/Grafana/Loki as products). Positioning: **NL glue + local evidence**, not “we reimplemented Grafana.”

### 1.3 Positioning (recruiter-ready one-liner)

**logpilot** is a **self-hosted, local-LLM assistant for Linux operations** that **grounds answers** in **ingested logs and read-only host probes**, with a path to **more connectors** over time—useful in a homelab and demonstrative of **safe AI + systems integration**.

---

## 2. Current codebase anchor (honest as-is)

Today the strongest pillar is **logs → Postgres + pgvector → RAG-style Q&A** (`README.md`). There are **read-only–oriented** behaviors: on-demand `journalctl`, optional Docker Engine inspect table, and **`disk_usage`** / **`cpu_thermal`** / **`gpu_status`** tools (typed contracts under `tools/`, host visibility and PATH-bound GPU CLIs) merged into answers when intent and settings allow. **`lm-sensors`-style subprocess probes**, extended Docker inspect, **systemd** and **network** summaries remain **planned** (Phase B/C), not a rename of the log stack.

---

## 3. Architecture direction: tools layer

### 3.1 Principle

Introduce (or consolidate behind) a **single internal “tools” or “probes” layer**:

- Each capability is a **named operation** with **typed inputs/outputs** (Pydantic or equivalent), **timeouts**, and **logging**.
- The LLM **does not** emit raw shell; it **selects tools** and **arguments** within a **schema** (function-calling or structured JSON), executed only if **allowlisted** for the deployment.

**Decision record:** see ADR `005_…` (tools vs raw shell, grounding).

### 3.2 Evidence contract

Every user-facing answer path should be able to record **what evidence was used** (for debugging and for future “show sources” UI): e.g. log line ids, tool name + redacted args hash + output snippet length.

### 3.3 Tool abstraction (interface sketch — pseudocode)

Illustrative Python shapes for Phase B; not a commitment to exact names.

```python
# Pseudocode only — naming illustrative

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

class ToolFailure(BaseModel):
    """Non-exception failure: safe to show to orchestration / logs (no secrets)."""
    code: str  # e.g. "timeout", "not_installed", "permission_denied", "parse_error", "unsupported_environment"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolEvidence(BaseModel):
    """Small summary for traces / future citation UI (§3.2)."""
    tool_name: str
    input_fingerprint: str  # hash of canonical JSON args, not raw env
    ok: bool
    duration_ms: float
    output_bytes: int
    failure: ToolFailure | None = None


class ToolRun(BaseModel):
    """Single invocation result."""
    evidence: ToolEvidence
    output: BaseModel | None = None  # validated connector output; None if failure


InT = TypeVar("InT", bound=BaseModel)
OutT = TypeVar("OutT", bound=BaseModel)


class ReadOnlyTool(ABC, Generic[InT, OutT]):
    """One allowlisted, typed, read-only operation."""

    name: str  # e.g. "disk_usage"
    version: int = 1
    input_model: type[InT]
    output_model: type[OutT]

    @abstractmethod
    async def run(self, params: InT, *, timeout_s: float) -> ToolRun:
        """
        Must enforce timeout (asyncio.wait_for or subprocess timeout).
        Must never raise for expected failures — return ToolRun with evidence.failure set.
        """
        ...


class ToolRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, ReadOnlyTool[Any, Any]] = {}

    def register(self, tool: ReadOnlyTool[Any, Any]) -> None:
        self._by_name[tool.name] = tool

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout_s: float,
    ) -> ToolRun:
        tool = self._by_name[name]
        params = tool.input_model.model_validate(arguments)
        return await tool.run(params, timeout_s=timeout_s)


# Example connector binding (still pseudocode)

class DiskUsageParams(BaseModel):
    timeout_s: float = 5.0
    mount_points: list[str] | None = None  # None = all (subject to product policy)

class MountInfo(BaseModel):
    source: str
    mountpoint: str
    size_b: int
    used_b: int
    avail_b: int
    use_pct: float | None = None

class DiskUsageResult(BaseModel):
    mounts: list[MountInfo]
    collected_at: str  # ISO-8601 UTC

class DiskUsageTool(ReadOnlyTool[DiskUsageParams, DiskUsageResult]):
    name = "disk_usage"
    input_model = DiskUsageParams
    output_model = DiskUsageResult

    async def run(self, params: DiskUsageParams, *, timeout_s: float) -> ToolRun:
        ...
```

### 3.4 Where tools run (resolved)

- **Host vs container:** Read-only tools execute **inside the logpilot container**. Host visibility is via **bind mounts** (read-only) into that container; each connector documents its **required mounts** in [`../agents/MAINTAIN.md`](../agents/MAINTAIN.md) (and linked operator docs as needed).
- **Single binary vs sidecar:** **Single binary / main image** for tools. A separate sidecar is **deferred** until Phase B is complete and image size is a **proven** problem.

---

## 4. Phased roadmap

### Phase A — Core reliability (now)

High-level themes: harden ingest / embed / query; keep `make check` green and **doctor** truthful; intent and planner admit missing data; README and ADR `005` stay the directional source of truth.

**Exit criteria:** Homelab operator can trust **log Q&A** and **doctor**; grounding rules are documented.

#### Phase A — concrete task list

Each task: files to touch, exact behavior, verification.

| ID | File(s) to change | What specifically changes | How to verify |
|----|-------------------|---------------------------|---------------|
| **A1** | This file (`local-sysadmin-copilot-roadmap.md`) | Document has no terminal paste above the title; Related links use normal markdown links. | Open file: title is first real heading; no shell transcript. |
| **A2** | `docs/plans/journal-host-visibility-doctor-and-parsed-service-fields.md` | Rewrite §1.3 “`logpilot doctor`” so it matches **current** `query/doctor.py` (journal ingest flag, `journalctl` on PATH, directory readability, optional `journalctl -n 0` probe, Docker socket hint, `--verbose` DB stats, conditional journal-empty WARN). Remove claims that doctor “does not” check items that already exist. | Reader is not told to add checks that are already implemented. |
| **A3** | `query/rag.py`, optionally `query/agent_loop.py` | When `agent=True`, after the planner finishes, if `resolved.source_scope != "all"` and **zero** log rows were collected, run **exactly one** extra retrieval with the same `since`, `top_k`, `min_level`, `source_contains`, keyword supplement, but `source_scope="all"`. Merge rows into the set used for the answer. If `debug=True`, append a trace step (e.g. `note: retry_after_empty_scoped_agent_search`) consistent with the non-agent path. | `make check`. Test mocks scoped empty then `all` non-empty; manual `ask … --agent --source-scope journal --debug` shows broadening when DB has only other families. |
| **A4** | `query/rag.py`, `query/cli.py`, `tests/test_rag_agent_journal.py`, `README.md` | **Decision (closed):** When `resolved.journalctl_on_demand` is true, **always** call `append_journalctl_for_query` and merge journal text into the answer context **even when `agent=True`** (same as non-agent). `logpilot ask --agent` help and README state that on-demand `journalctl` still runs when intent enables it. | `make check`. `tests/test_rag_agent_journal.py`; `logpilot ask --help` mentions journalctl with `--agent`. |
| **A5** | `query/rag.py` (`_empty_retrieval_message`) | When returning “no log lines matched…”, optionally add one sentence if a cheap DB check shows rows in-window with `embedding IS NULL` and not failed (embed backlog)—**or** if too heavy, add the same signal only under `debug=True` in trace metadata. | `make check`. Test with fixture rows pending embed. |
| **A6** | `query/agent_loop.py` (`PLANNER_SYSTEM`) | Add an explicit rule: if `rows_fetched_so_far` is 0 and `working_source_scope` is not `all`, prefer a `search_logs` with `source_scope: "all"` once before `finish` (unless `list_sources` is clearly needed). | `make check`. Lightweight test or assertion that the system string includes the rule. |
| **A7** | `README.md` | Add a short **Grounding** subsection: answers from retrieved logs, optional read-only host/Docker snippets, or explicit “no data”; no arbitrary shell; links to ADR `005` and this roadmap. | Manual + `make check`. |
| **A8** | `query/rag.py` | When `debug=True`, add `evidence_summary` to trace: sample `retrieved_row_ids`, counts, flags for journalctl/docker extras and char lengths, `broadened_scope_after_empty` / agent retry flags. No raw log bodies. | `make check`. Test + `POST /query?debug=true` includes block. |
| **A9** | `ingestor/docker_json.py`, `ingestor/plain_text.py`, `embedder/worker.py` (as needed) | Targeted reliability: fix **specific** bugs found by review (not vague “harden”); each fix has a test or log assertion. If none found, note in Phase A checklist “reviewed; no change.” | `make check` + any new tests. |

### Phase B — Read connectors (incremental)

Add **read-only** probes behind the tools layer, one family at a time, each with **tests** and **docs** (`MAINTAIN` matrix):

| Connector (examples)    | Notes                                                         |
| ----------------------- | ------------------------------------------------------------- |
| Disk / filesystem usage | `df`, mount points; normalize for prompts                     |
| CPU / thermal           | sysfs, `sensors`, `/proc`—best-effort per host                |
| GPU                     | `nvidia-smi` / ROCm when present; degrade gracefully          |
| Docker / Podman         | Extend read-only inspect beyond today’s table where useful    |
| systemd                 | `systemctl show` / unit states (read-only)                    |
| Network (cautious)      | Only non-destructive summaries (e.g. `ip -br link`) if agreed |

#### Phase B — first connector to implement

**Name:** `disk_usage` (disk / filesystem usage).

**Spec:** Run a **read-only** view of mounted filesystems for NL answers: parse stable `df` output (e.g. `df -B1 -P`) **inside the logpilot container** (§3.4); document required bind mounts in MAINTAIN. Return **structured records** per mount: device or pseudo-fs identifier, mount point, size, used, available, use percentage when present, plus a **short human summary** for prompts. Enforce a **hard timeout** (e.g. 5s). On missing `df`, non-zero exit, or timeout, return a **typed failure** so the answer path can say “disk probe unavailable” instead of inventing numbers. Optionally allow an allowlisted **set of mount points** (e.g. `/`, `/home`) to limit noise and sensitivity. Ship **tests** with golden `df` fixtures and **MAINTAIN** updates (`.env.example` only if new settings).

**Exit criteria (Phase B):** Model can answer **a bounded set** of “status” questions **from tool output**, with **no answer** when tools are unavailable.

### Phase C — Orchestration (“model manages the tool”)

- **Structured planner** chooses: which tools to run, **which query flags** / scopes map to user intent (today’s intent LLM evolves toward **tool calls + retrieval**, not free text).
- **Bounded steps** and **timeouts** (already partially reflected in `QUERY_AGENT_*` env vars).
- Optional: **safe config surface** (e.g. API to toggle feature flags with validation)—**only** after read-path is mature.

**Exit criteria:** Repeatable traces for multi-step runs; clear caps on cost/latency.

### Phase D — Experience layer (later)

- **Web or desktop UI** with **chat history**, **sessions**, optional **memory** (with explicit retention policy).
- **Citation UI** for log lines and tool outputs.

**Exit criteria:** Portfolio demo you can walk through in an interview.

---

## 5. Security and portfolio narrative

- **Read-only by default**; mount **least privilege** (continue documenting journal/socket trade-offs in README).
- **Document** each connector’s **data sensitivity** and **failure modes** (e.g. no NVIDIA driver → “GPU probe unavailable”).
- Prefer **one ADR per major connector or policy** (`docs/decisions/`) so agents do not re-litigate.

---

## 6. Implementation hygiene (agents + humans)

- Small, explicit tasks; after substantive code changes run `make check` (or enable `make install-git-hooks` for pre-push).
- Cross-cutting choices → `docs/decisions/` (template in [`../decisions/README.md`](../decisions/README.md)).
- Full checklist: [`../agents/MAINTAIN.md`](../agents/MAINTAIN.md).
