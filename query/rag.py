from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

from sqlalchemy import and_, func, select

from db.models import Log
from db.session import session_scope
from logpilot.settings import get_settings
from query.agent_loop import run_bounded_retrieval_planner
from query.cpu_thermal_on_demand import append_cpu_thermal_for_query
from query.disk_usage_on_demand import append_disk_usage_for_query
from query.gpu_status_on_demand import append_gpu_status_for_query
from query.docker_on_demand import append_docker_engine_for_query
from query.host_services_on_demand import append_host_services_for_query
from query.inventory import build_inventory_block_for_prompt, embedded_row_counts_by_family
from query.journalctl_on_demand import append_journalctl_for_query
from query.intent import ResolvedQuery, resolve_query_params
from query.ollama_chat import ollama_chat
from query.retrieval import SearchParams, search_logs
from query.since_parse import parse_since

logger = logging.getLogger(__name__)


async def _pending_embed_count_in_window(*, since: str) -> int:
    """Rows in the retrieval window with no embedding yet (not failed) — cheap COUNT for operator hints."""
    cutoff = parse_since(since)
    async with session_scope() as session:
        stmt = (
            select(func.count())
            .select_from(Log)
            .where(
                and_(
                    Log.timestamp >= cutoff,
                    Log.embedding.is_(None),
                    Log.embedding_failed.is_(False),
                )
            )
        )
        return int((await session.execute(stmt)).scalar() or 0)


def _context_annotation(parsed: dict) -> str:
    """Short hints from ingest `parsed` JSON for RAG (service_key, unit, container name, etc.)."""
    if not parsed:
        return ""
    parts: list[str] = []
    sk = parsed.get("service_key")
    if sk:
        parts.append(f"service_key={sk}")
    sl = parsed.get("service_label")
    if sl and sl != sk:
        parts.append(f"service_label={sl}")
    for key in ("container_name", "systemd_unit", "syslog_identifier", "unit", "_COMM"):
        val = parsed.get(key)
        if val:
            parts.append(f"{key}={val}")
    if not parts:
        return ""
    return " [" + "; ".join(parts) + "]"


def _redact_for_llm(text: str) -> str:
    s = get_settings()
    pat = (s.query_context_redact_regex or "").strip()
    if not pat:
        return text
    try:
        return re.sub(pat, "[REDACTED]", text)
    except re.error:
        logger.warning("invalid QUERY_CONTEXT_REDACT_REGEX; skipping redaction")
        return text


def _format_rows_for_prompt(rows: list[Log]) -> str:
    lines: list[str] = []
    for r in rows:
        ann = _context_annotation(r.parsed or {})
        raw = r.raw[:4000] if r.raw else ""
        lines.append(f"- {r.timestamp.isoformat()} | {r.source}{ann} | {raw}")
    return "\n".join(lines)


_ANSWER_SYSTEM_PROMPT = (
    "Be a concise log analyst for one Linux host. Answer in direct statements; do not restate these instructions. "
    "Do not describe the evidence as a 'dump', 'log file type', or similar meta-commentary. "
    "Do not open with chatty framing ('You're looking for', 'Let's break it down', 'I can help you interpret'). "
    "Answer only the operator's actual question—do not invent numbered sub-questions "
    "(e.g. '1. What is the Linux host… 2. What is the purpose of the log file…') unless they asked those explicitly. "
    "If the user asks what log/data coverage or access you have, lead with ingestion configuration and stored families "
    "(inventory facts)—not a story mined from a few retrieved lines. "
    "If the evidence does not speak to the question, say so clearly. "
    "If the sample is mostly unrelated infrastructure noise (e.g. repeated HTTP access to `/api/chat` or `/api/embeddings`, "
    "generic Gin/Ollama traffic, intent/JSON parse errors from this app) but the user asked about a different topic "
    "(Apache, SSH, nginx, SELinux, AppArmor, VPN, databases, cron, etc.), "
    "say that topic does not appear in the sample—do not pivot the answer to the unrelated traffic or app internals. "
    "Do not pad with textbook definitions of technologies (what SELinux is, what AVC means, etc.) unless the log lines "
    "themselves discuss them; at most one short clause if needed. "
    "Do not invent events, severities, or paths beyond what the lines support. "
    "Do not confuse unrelated concepts: e.g. 'killing FFmpeg process' or 'client disconnected' in app logs "
    "are not the kernel OOM killer or Ethernet carrier loss unless the text explicitly says so; "
    "GPU probe failures are not sudo or SSH authentication unless the text explicitly says so."
)

# Appended to every answer-step user message so the chat model cannot “helpfully” invent FAQs.
_ANSWER_USER_TAIL = (
    "\n\nAnswer format: plain prose only—address the single question above. "
    'Do **not** write "Here are the answers to your questions", "Here are the key points", or any numbered list of '
    "questions you invented. No Q&A numbering unless the user's message already used that structure.\n"
)


async def ollama_answer(prompt: str) -> str:
    return await ollama_chat(
        [
            {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )


def _extract_docker_rows(docker_extra: str) -> int | None:
    text = docker_extra.strip()
    if not text:
        return None
    # Header row + separator + data rows.
    table_rows = sum(1 for line in text.splitlines() if line.strip().startswith("| "))
    data_rows = max(0, table_rows - 2)
    return data_rows


def _extract_docker_state_summary(docker_extra: str) -> str | None:
    """Return 'X running, Y exited, ...' from Docker inspect table if present."""
    text = docker_extra.strip()
    if not text:
        return None
    state_counts: dict[str, int] = {}
    for line in text.splitlines():
        if not line.strip().startswith("| "):
            continue
        cols = [c.strip() for c in line.split("|")]
        # Table rows look like: | name | id | state | restart | started | finished |
        if len(cols) < 5:
            continue
        state = cols[3].lower()
        if state in ("state", "---", ""):
            continue
        state_counts[state] = state_counts.get(state, 0) + 1
    if not state_counts:
        return None
    ordered = sorted(state_counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ", ".join(f"{count} {state}" for state, count in ordered)


def _extract_root_disk_usage(disk_extra: str) -> str | None:
    # Markdown table row from disk_usage probe:
    # | `/dev/sda1` | `/` | 47% | 123 | 456 | 789 |
    for line in disk_extra.splitlines():
        if not line.strip().startswith("| "):
            continue
        cols = [c.strip().strip("`") for c in line.split("|")]
        if len(cols) < 5:
            continue
        mount = cols[2]
        use_pct = cols[3]
        if mount == "/" and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?%", use_pct):
            return use_pct
    return None


def _extract_load_avg(cpu_extra: str) -> str | None:
    for line in cpu_extra.splitlines():
        if "Load average (1m / 5m / 15m)" not in line:
            continue
        m = re.search(r"([0-9.]+)\s*/\s*([0-9.]+)\s*/\s*([0-9.]+)", line)
        if m:
            return f"{m.group(1)} / {m.group(2)} / {m.group(3)}"
    return None


def _deterministic_meta_answer(
    *,
    counts: dict[str, int],
    docker_extra: str,
    disk_extra: str,
    cpu_thermal_extra: str,
    gpu_extra: str,
) -> str:
    total = sum(max(0, int(counts.get(k, 0))) for k in ("journal", "docker", "file", "other"))
    lines = [
        (
            "Embedded line totals currently stored in Postgres: "
            f"{total:,} total "
            f"(journal: {int(counts.get('journal', 0)):,}, "
            f"docker: {int(counts.get('docker', 0)):,}, "
            f"file: {int(counts.get('file', 0)):,}, "
            f"other: {int(counts.get('other', 0)):,})."
        ),
    ]

    docker_rows = _extract_docker_rows(docker_extra)
    docker_states = _extract_docker_state_summary(docker_extra)
    if docker_rows is not None:
        if docker_states:
            lines.append(
                "Docker Engine live inspect is available for this question "
                f"({docker_rows} containers in the table: {docker_states})."
            )
        else:
            lines.append(
                f"Docker Engine live inspect is available for this question ({docker_rows} containers in the table)."
            )
    else:
        lines.append("Docker Engine live inspect was not included for this question.")

    root_pct = _extract_root_disk_usage(disk_extra)
    if root_pct:
        lines.append(f"Disk usage probe is available; root filesystem `/` is at {root_pct} used.")
    elif disk_extra.strip():
        lines.append("Disk usage probe is available (read-only `df` capacity data).")
    else:
        lines.append("Disk usage probe was not included for this question.")

    load_avg = _extract_load_avg(cpu_thermal_extra)
    if load_avg:
        lines.append(f"CPU/thermal probe is available; load average is {load_avg}.")
    elif cpu_thermal_extra.strip():
        lines.append("CPU/thermal probe is available (load average and visible thermal data).")
    else:
        lines.append("CPU/thermal probe was not included for this question.")

    if "not_installed" in gpu_extra:
        lines.append("GPU probe ran, but no GPU tooling/data is available in this environment (`nvidia-smi` / `rocm-smi`).")
    elif gpu_extra.strip():
        lines.append("GPU probe is available for this question.")
    else:
        lines.append("GPU probe was not included for this question.")

    return "\n".join(lines)


def _should_collect_host_services(*, resolved: ResolvedQuery, user_text: str) -> bool:
    t = user_text.lower()
    if resolved.is_meta_coverage_question:
        return True
    if resolved.source_contains:
        return True
    service_markers = ("service", "daemon", "systemctl", "working properly", "status")
    return any(m in t for m in service_markers)


def _compose_answer_context(
    *,
    docker_extra: str,
    disk_extra: str,
    cpu_thermal_extra: str,
    gpu_extra: str,
    j_extra: str,
    base_rows: str,
    resolved: ResolvedQuery,
    journalctl_list_boots: bool,
) -> str:
    """Order: Docker, disk, CPU/thermal, GPU, journal, similarity sample — with reboot headers when needed."""
    d = docker_extra.strip()
    k = disk_extra.strip()
    c = cpu_thermal_extra.strip()
    g = gpu_extra.strip()
    j = j_extra.strip()
    b = base_rows.strip()

    def _structured_probe_prefix() -> str:
        return "\n\n".join(x for x in (d, k, c, g) if x)

    if j and resolved.reboot_journal_focus and journalctl_list_boots and resolved.include_inventory_context:
        middle = (
            "## Host evidence (reboot / boot-session counts — authoritative)\n\n"
            f"{j}\n\n"
            "## Retrieved log lines (similarity sample only — not for counting host reboots)\n\n"
            f"{b}"
        )
        pre = _structured_probe_prefix()
        return f"{pre}\n\n{middle}" if pre else middle

    if j and resolved.reboot_journal_focus:
        tail = f"{j}\n\n---\n\n{b}" if b else j
        pre = _structured_probe_prefix()
        return f"{pre}\n\n{tail}" if pre else tail

    chunks: list[str] = []
    for x in (d, k, c, g, j, b):
        if x:
            chunks.append(x)
    return "\n\n".join(chunks)


@dataclass(frozen=True)
class QueryResult:
    answer: str
    trace: list[dict[str, object]] | None = None
    #: Full user message sent to the chat model for the answer step (RAG prompt). For SFT export when enabled.
    answer_prompt: str | None = None


async def ask_question_from_prompt(
    user_text: str,
    since: str | None = None,
    top_k: int | None = None,
    *,
    source_scope: str | None = None,
    min_level: str | None = None,
    source_contains: str | None = None,
    use_intent: bool = True,
    agent: bool = False,
    debug: bool = False,
) -> QueryResult:
    """Resolve natural-language parameters (unless disabled), then run RAG (optionally multi-step)."""
    resolved = await resolve_query_params(
        user_text,
        since,
        top_k,
        source_scope_override=source_scope,
        min_level_override=min_level,
        source_contains_override=source_contains,
        use_intent=use_intent,
    )
    return await ask_question_resolved(resolved, user_text=user_text, agent=agent, debug=debug)


async def ask_question_resolved(
    resolved: ResolvedQuery,
    *,
    user_text: str,
    agent: bool = False,
    debug: bool = False,
) -> QueryResult:
    s = get_settings()
    broadened_scope = False
    agent_empty_scope_retry = False
    if agent and s.query_agent_max_steps > 0:
        rows, trace = await run_bounded_retrieval_planner(
            user_text,
            resolved,
            max_steps=s.query_agent_max_steps,
            max_total_rows=s.query_agent_max_total_rows,
            timeout_s=s.query_agent_timeout_s,
        )
        trace_out: list[dict[str, object]] | None = trace if debug else None
        if not rows and resolved.source_scope != "all":
            logger.info(
                "empty agent retrieval for source_scope=%s; retrying once with source_scope=all",
                resolved.source_scope,
            )
            params_all = SearchParams(
                since=resolved.since,
                top_k=resolved.top_k,
                source_scope="all",
                min_level=resolved.min_level,
                source_contains=resolved.source_contains,
            )
            result_all = await search_logs(
                resolved.question,
                params_all,
                keyword_supplement=resolved.use_keyword_supplement,
            )
            rows = result_all.rows
            broadened_scope = True
            agent_empty_scope_retry = True
            if debug and trace_out is not None:
                trace_out.append(
                    {
                        "step": "search_logs",
                        "row_count": len(rows),
                        "duration_ms": result_all.duration_ms,
                        "note": "retry_after_empty_scoped_agent_search",
                        "params": {
                            "since": params_all.since,
                            "top_k": params_all.top_k,
                            "source_scope": params_all.source_scope,
                            "min_level": params_all.min_level,
                            "source_contains": params_all.source_contains,
                        },
                    }
                )
    else:
        params = SearchParams(
            since=resolved.since,
            top_k=resolved.top_k,
            source_scope=resolved.source_scope,
            min_level=resolved.min_level,
            source_contains=resolved.source_contains,
        )
        result = await search_logs(
            resolved.question,
            params,
            keyword_supplement=resolved.use_keyword_supplement,
        )
        rows = result.rows
        trace_steps: list[dict[str, object]] = []
        if debug:
            trace_steps.append(
                {
                    "step": "search_logs",
                    "row_count": len(rows),
                    "duration_ms": result.duration_ms,
                    "params": {
                        "since": params.since,
                        "top_k": params.top_k,
                        "source_scope": params.source_scope,
                        "min_level": params.min_level,
                        "source_contains": params.source_contains,
                    },
                }
            )
        if not rows and resolved.source_scope != "all":
            logger.info(
                "empty retrieval for source_scope=%s; retrying once with source_scope=all",
                resolved.source_scope,
            )
            params_all = SearchParams(
                since=resolved.since,
                top_k=resolved.top_k,
                source_scope="all",
                min_level=resolved.min_level,
                source_contains=resolved.source_contains,
            )
            result = await search_logs(
                resolved.question,
                params_all,
                keyword_supplement=resolved.use_keyword_supplement,
            )
            rows = result.rows
            broadened_scope = True
            if debug:
                trace_steps.append(
                    {
                        "step": "search_logs",
                        "row_count": len(rows),
                        "duration_ms": result.duration_ms,
                        "note": "retry_after_empty_scoped_search",
                        "params": {
                            "since": params_all.since,
                            "top_k": params_all.top_k,
                            "source_scope": params_all.source_scope,
                            "min_level": params_all.min_level,
                            "source_contains": params_all.source_contains,
                        },
                    }
                )
        trace_out = trace_steps if debug else None

    journal_coro = append_journalctl_for_query(
        resolved.since,
        journalctl_on_demand=resolved.journalctl_on_demand,
        reboot_journal_focus=resolved.reboot_journal_focus,
        source_contains=resolved.source_contains,
    )
    (docker_extra, docker_excerpt_len), (
        j_extra,
        journalctl_excerpt_len,
        journalctl_list_boots,
    ), (disk_extra, disk_excerpt_len), (
        cpu_thermal_extra,
        cpu_thermal_excerpt_len,
    ), (gpu_extra, gpu_excerpt_len), host_services_probe = await asyncio.gather(
        append_docker_engine_for_query(resolved.docker_engine_on_demand),
        journal_coro,
        append_disk_usage_for_query(resolved.disk_usage_on_demand),
        append_cpu_thermal_for_query(resolved.cpu_thermal_on_demand),
        append_gpu_status_for_query(resolved.gpu_status_on_demand),
        append_host_services_for_query(
            enable=_should_collect_host_services(resolved=resolved, user_text=user_text),
            source_contains=resolved.source_contains,
            question=user_text,
        ),
    )
    host_services_extra = host_services_probe.block
    host_services_excerpt_len = host_services_probe.chars

    if debug and trace_out is not None:
        trace_out.append(
            {
                "step": "docker_engine_on_demand",
                "chars": docker_excerpt_len,
                "intent": resolved.docker_engine_on_demand,
            }
        )
        trace_out.append(
            {
                "step": "disk_usage_on_demand",
                "chars": disk_excerpt_len,
                "intent": resolved.disk_usage_on_demand,
            }
        )
        trace_out.append(
            {
                "step": "cpu_thermal_on_demand",
                "chars": cpu_thermal_excerpt_len,
                "intent": resolved.cpu_thermal_on_demand,
            }
        )
        trace_out.append(
            {
                "step": "gpu_status_on_demand",
                "chars": gpu_excerpt_len,
                "intent": resolved.gpu_status_on_demand,
            }
        )

    embed_pending_in_window = 0
    if not rows:
        try:
            embed_pending_in_window = await _pending_embed_count_in_window(since=resolved.since)
        except ValueError:
            logger.debug("invalid since for embed backlog check: %s", resolved.since)
        except Exception:
            logger.warning("pending embed count query failed", exc_info=True)

    if debug and trace_out is not None:
        trace_out.append(
            {
                "step": "evidence_summary",
                "retrieved_row_count": len(rows),
                "retrieved_row_ids_sample": [r.id for r in rows[:25]],
                "journalctl_on_demand": resolved.journalctl_on_demand,
                "journalctl_excerpt_chars": journalctl_excerpt_len,
                "docker_engine_on_demand": resolved.docker_engine_on_demand,
                "docker_excerpt_chars": docker_excerpt_len,
                "disk_usage_on_demand": resolved.disk_usage_on_demand,
                "disk_excerpt_chars": disk_excerpt_len,
                "cpu_thermal_on_demand": resolved.cpu_thermal_on_demand,
                "cpu_thermal_excerpt_chars": cpu_thermal_excerpt_len,
                "gpu_status_on_demand": resolved.gpu_status_on_demand,
                "gpu_status_excerpt_chars": gpu_excerpt_len,
                "host_services_excerpt_chars": host_services_excerpt_len,
                "broadened_scope_after_empty": broadened_scope,
                "agent_empty_scope_retry": agent_empty_scope_retry,
                "embed_pending_in_window": embed_pending_in_window,
            }
        )

    empty_msg = _empty_retrieval_message(
        resolved,
        rows,
        broadened_scope=broadened_scope,
        embed_pending_in_window=embed_pending_in_window,
    )
    if (
        empty_msg
        and not docker_extra.strip()
        and not j_extra.strip()
        and not disk_extra.strip()
        and not cpu_thermal_extra.strip()
        and not gpu_extra.strip()
        and not host_services_extra.strip()
    ):
        return QueryResult(answer=empty_msg, trace=trace_out, answer_prompt=None)

    if not rows and resolved.source_contains and host_services_probe.summary_line:
        answer = _no_logs_with_live_systemd_answer(
            source_contains=resolved.source_contains,
            since=resolved.since,
            summary_line=host_services_probe.summary_line,
            embed_pending_in_window=embed_pending_in_window,
        )
        return QueryResult(answer=answer, trace=trace_out, answer_prompt=None)

    base_rows = _redact_for_llm(_format_rows_for_prompt(rows))
    if resolved.is_meta_coverage_question:
        # Without this, small LLMs narrate the similarity sample as if it were the inventory block.
        base_rows = (
            "_(Similarity-retrieved log lines are **omitted** for catalog questions. Use only the **## Ingestion "
            "configuration** / **## What is actually stored** sections at the top of this prompt, plus live probe "
            "subsections in the context below.)_"
        )
    context = _compose_answer_context(
        docker_extra=docker_extra,
        disk_extra=disk_extra,
        cpu_thermal_extra=cpu_thermal_extra,
        gpu_extra=gpu_extra,
        j_extra=(f"{host_services_extra}\n\n{j_extra}".strip() if host_services_extra.strip() else j_extra),
        base_rows=base_rows,
        resolved=resolved,
        journalctl_list_boots=journalctl_list_boots,
    )
    if resolved.include_inventory_context and resolved.is_meta_coverage_question:
        try:
            counts = await embedded_row_counts_by_family()
        except Exception:
            logger.warning("meta deterministic answer: embedded counts unavailable", exc_info=True)
            counts = {"journal": 0, "docker": 0, "file": 0, "other": 0}
        return QueryResult(
            answer=_deterministic_meta_answer(
                counts=counts,
                docker_extra=docker_extra,
                disk_extra=disk_extra,
                cpu_thermal_extra=cpu_thermal_extra,
                gpu_extra=gpu_extra,
            ),
            trace=trace_out,
            answer_prompt=None,
        )

    if resolved.include_inventory_context:
        inventory = await build_inventory_block_for_prompt(
            user_text,
            journalctl_excerpt_len=journalctl_excerpt_len,
            journalctl_list_boots=journalctl_list_boots,
            docker_engine_excerpt_len=docker_excerpt_len,
            disk_usage_excerpt_len=disk_excerpt_len,
            cpu_thermal_excerpt_len=cpu_thermal_excerpt_len,
            gpu_status_excerpt_len=gpu_excerpt_len,
            is_meta_coverage_question=resolved.is_meta_coverage_question,
            reboot_journal_focus=resolved.reboot_journal_focus,
            journalctl_on_demand=resolved.journalctl_on_demand,
        )
        label = (
            "Retrieved log lines (small similarity sample — not a full catalog)"
            if resolved.is_meta_coverage_question
            else "Retrieved log lines"
        )
        if resolved.is_meta_coverage_question:
            intro = (
                "**Coverage / what-data question:** The prompt already contains markdown sections titled **"
                "## Ingestion configuration (authoritative)** and **## What is actually stored (embedded rows in Postgres)**. "
                "Paraphrase **only** those headings’ bullets (env flags, paths, **embedded row counts by family**, embed backlog). "
                "**Never** invent “ingestion configuration” from PostgreSQL checkpoint lines, WAL timing, HTTP /health traffic, "
                "or similarity-sample noise—those are **not** the inventory block.\n"
                "**Answer order — hard rule:** The **very first sentence** of your reply must state **what is stored** in Postgres "
                "(name the families **journal / docker / file / other** and their **embedded line counts** from **## What is "
                "actually stored**). If your first sentence instead names **Docker Engine**, **disk**, **CPU**, **GPU**, or "
                "**probes**, the answer is **wrong**; rewrite so storage counts come first. Your **second** paragraph may cover "
                "**## Ingestion configuration** (paths, env flags). **Then** summarize live probes.\n"
                "**Banned openers** (do **not** use): “based on the **log** data”, “from the **logs** below”, “the provided **log** "
                "lines”, “The logs I have access to include…”, “according to the retrieved lines” — for this question the "
                "similarity sample is **omitted**; you are answering from **inventory + live probes**, not a log paste. "
                "**Do not** echo the user’s question as a title, rhetorical question, or FAQ line.\n"
                "**Logpilot is not logs-only:** The context block usually includes **live read-only probes** for this question—"
                "**Disk usage** (`df` table), **CPU load and thermal**, **GPU status**, **Docker Engine** inspect. After the "
                "inventory paragraph, summarize **only what those probe sections actually show**. Do **not** "
                "label a checkpoint “duration” in seconds as “disk usage”. If a subsection is absent, say it was not included.\n"
                f"The trailing “{label}” note is **not** raw log text—similarity lines are **omitted** for catalog questions. "
                "**Do not** claim you read a log excerpt.\n"
            )
            if resolved.docker_engine_on_demand and not docker_extra.strip():
                intro += (
                    "**Docker Engine lifecycle:** There is **no** **Docker Engine — live read-only inspect** table in the "
                    "context below (Docker socket unavailable, `DOCKER_QUERY_ON_DEMAND` off, or nothing to inspect). "
                    "Say that clearly. Do **not** describe `RestartCount`, running state, or a `docker ps` overview from "
                    "log line hints alone.\n"
                )
        else:
            intro = (
                "Use the inventory and **Internal constraints** sections as silent guidance only. "
                "Treat ingestion settings and embedded row counts as facts; do not invent host-wide coverage.\n"
            )
        if journalctl_list_boots:
            intro += (
                "For **host OS reboot / how many times the machine booted** questions, trust the **`journalctl --list-boots`** section; "
                "do **not** infer host reboot counts from package hooks, `file:` logs, or Docker lines in the sample.\n"
            )
        if docker_extra.strip():
            intro += (
                "For **container restarts, `RestartCount`, running/stopped state, and container uptime (`StartedAt`)**, "
                "trust the **Docker Engine — live read-only inspect** table. **`RestartCount` is cumulative since container "
                "creation**, not necessarily “today” unless the user accepts that definition. Do **not** infer those numbers "
                "from similarity log lines when the table is present.\n"
            )
        if disk_extra.strip():
            intro += (
                "For **disk space, usage %, and mount capacity only**, trust the **Disk usage** section from the read-only "
                "`disk_usage` probe (`df`) when present; it does **not** measure I/O load. Do **not** infer capacity from "
                "log lines.\n"
            )
        if base_rows.strip() and not resolved.is_meta_coverage_question:
            intro += (
                "Retrieved lines may include **database or app internals** (e.g. PostgreSQL *checkpoint*, *WAL*). Those "
                "describe **that service’s** persistence work, **not** whether the user’s host disk is I/O-bound. "
                "If the question is about **disk busy / HDD load** and there is no `iostat`-class evidence, say this "
                "tool does not measure I/O saturation—do **not** spin a story from checkpoint logs alone.\n"
            )
        if cpu_thermal_extra.strip():
            intro += (
                "For **load average and thermal zone temperatures**, trust the **CPU load and thermal** section from "
                "the read-only `cpu_thermal` probe when present; do **not** infer temps from log lines.\n"
            )
        if gpu_extra.strip():
            intro += (
                "For **GPU utilization, VRAM, and GPU temperature**, trust the **GPU status** section from the "
                "read-only `gpu_status` probe (`nvidia-smi` / `rocm-smi`) when present; do **not** infer GPU stats "
                "from log lines.\n"
            )
        prompt = (
            f"{inventory}\n---\n"
            f"{intro}"
            "Write a natural answer for a human operator (a few short paragraphs at most). "
            "Respond directly to the **Question** line below only—no fabricated FAQ or numbered sub-questions.\n"
            "**Do not** quote, paste, or markdown-copy the sections above—especially not **Internal constraints**. "
            "Never say the words **internal constraints** in the answer. "
            "Summarize conclusions in your own words.\n\n"
            f"Question: {resolved.question}\n\n"
        )
        if (
            journalctl_list_boots
            or docker_extra.strip()
            or disk_extra.strip()
            or cpu_thermal_extra.strip()
            or gpu_extra.strip()
        ):
            if resolved.is_meta_coverage_question:
                prompt += (
                    "Context (live read-only probes first; last block is a short note that similarity log lines "
                    f"were omitted — not a log excerpt):\n{context}\n"
                )
            else:
                prompt += (
                    f"Context (structured host/docker/disk/CPU/GPU evidence first, then {label.lower()}):\n{context}\n"
                )
        else:
            prompt += f"{label}:\n{context}\n"
    else:
        if (
            docker_extra.strip()
            or j_extra.strip()
            or disk_extra.strip()
            or cpu_thermal_extra.strip()
            or gpu_extra.strip()
        ):
            prompt = (
                "Answer using the evidence below (Docker Engine inspect, disk usage (`df` — capacity only, not I/O load), "
                "CPU load/thermal probe, GPU status (`nvidia-smi` / `rocm-smi`), host journal output, and/or retrieved "
                "log lines as applicable). "
                "For container `RestartCount` and state, trust the Docker table when present; for host boots, trust "
                "`journalctl` when present; for disk **capacity**, trust Disk usage; for load/temperature, trust "
                "CPU/thermal; for GPU metrics, trust GPU status. "
                "Do **not** use database checkpoint/WAL-style log lines to infer the host HDD is under I/O load.\n\n"
                f"Question: {resolved.question}\n\n"
                f"Evidence:\n{context}\n"
            )
        else:
            prompt = (
                "Answer using only the log lines below. If they are not enough to answer, say so. "
                "Do **not** treat checkpoint/WAL/database persistence messages as measuring the host disk’s I/O load "
                "unless the user explicitly asked about that service.\n\n"
                f"Question: {resolved.question}\n\n"
                f"Logs:\n{context}\n"
            )
    if resolved.include_inventory_context and resolved.is_meta_coverage_question:
        prompt += (
            "\n\n**Required structure:** (1) **Opening:** the **first sentence** must give **embedded line totals** and "
            "**per-family counts** (journal / docker / file / other) **exactly as in ## What is actually stored**. "
            "(1b) **Next** paraphrase **## Ingestion configuration** (env flags, paths). Opening with probes only, or phrases "
            "like “log data” / “logs I have access to”, **fails** this requirement. (2) **Then** short factual "
            "lines for **Disk usage** / **CPU load and thermal** / **GPU status** / **Docker Engine** **only** from their "
            "dedicated subsections in the context below (`df` mounts, loadavg, sensors, `nvidia-smi`/`rocm-smi`, "
            "`docker inspect`). **Never** mine those facts from arbitrary log lines. (3) **End cleanly:** either **omit** "
            "log-line anecdotes entirely, or add **one short** concrete clause (a real ingested family, e.g. docker JSON logs) "
            "if it helps. **Do not** finish with vague offers such as “I can provide an optional example”, “if requested”, or "
            "“similarity sample” without naming a concrete fact.\n"
        )
    prompt = prompt.rstrip() + _ANSWER_USER_TAIL
    try:
        if s.query_answer_timeout_s > 0:
            answer = await asyncio.wait_for(ollama_answer(prompt), timeout=s.query_answer_timeout_s)
        else:
            answer = await ollama_answer(prompt)
        return QueryResult(answer=answer, trace=trace_out, answer_prompt=prompt)
    except asyncio.TimeoutError:
        logger.warning("answer LLM timed out after %ss", s.query_answer_timeout_s)
        return QueryResult(
            answer="Retrieval succeeded but the answer step timed out. Try a narrower question or smaller --top-k.",
            trace=trace_out,
            answer_prompt=prompt,
        )
    except Exception as exc:
        logger.exception("chat failed")
        return QueryResult(
            answer=f"Retrieval succeeded but LLM call failed: {exc}",
            trace=trace_out,
            answer_prompt=prompt,
        )


def _embed_backlog_clause(embed_pending_in_window: int) -> str:
    if embed_pending_in_window <= 0:
        return ""
    if embed_pending_in_window >= 10_000:
        return (
            " A large embedding backlog remains in this time window (many rows still lack vectors), so similarity "
            "search can look empty even when raw log rows already exist in the database."
        )
    return (
        f" {embed_pending_in_window} log row(s) in this window still lack embeddings; similarity search may miss "
        "matches until the embed worker catches up."
    )


def _all_units_report_not_loaded(summary_line: str) -> bool:
    parts = [p.strip() for p in summary_line.split(";") if p.strip()]
    return bool(parts) and all("not loaded" in p for p in parts)


def _no_logs_with_live_systemd_answer(
    *,
    source_contains: str,
    since: str,
    summary_line: str,
    embed_pending_in_window: int,
) -> str:
    """When DB retrieval is empty but we have a live systemd snapshot, lead with that evidence."""
    log_note = (
        f"No ingested lines matched `{source_contains}` for vector search in `{since}` "
        "(nothing embedded in that slice, journal wording may differ e.g. `smbd` vs `samba`, or filters are narrow)."
    )
    lead = summary_line.rstrip(".")
    out = f"From live systemd: {lead}. {log_note}{_embed_backlog_clause(embed_pending_in_window)}"
    if "not usable in this runtime" in summary_line.lower():
        out += (
            " For native unit state (e.g. whether Samba is running), run `logpilot ask` on the host where systemd "
            "is init (PID 1), or use logs ingested from that host."
        )
    elif _all_units_report_not_loaded(summary_line):
        out += (
            ' Here **"not loaded"** means those unit names are not in host systemd right now (often uninstalled, '
            "disabled, or Samba runs only in a container). It does not by itself mean a broken share if you never "
            "ran Samba as a host service."
        )
    return out


def _empty_retrieval_message(
    resolved: ResolvedQuery,
    rows: list[Log],
    *,
    broadened_scope: bool = False,
    embed_pending_in_window: int = 0,
) -> str:
    if rows:
        return ""
    hint = ""
    if broadened_scope:
        hint += (
            " Intent suggested a narrow log family, but it had no embedded lines; "
            "retrieval was retried with source_scope=all and still found nothing."
        )
    elif resolved.source_scope != "all":
        hint += (
            f" (source_scope={resolved.source_scope!r}; nothing matched or not embedded yet — "
            f"enable {resolved.source_scope!r} ingestion or use --source-scope all)"
        )
    if resolved.min_level:
        hint += f" (min_level={resolved.min_level!r}; many lines have no level — try clearing min_level for Docker logs)"
    if resolved.source_contains:
        hint += f" (source_contains={resolved.source_contains!r})"
    if not hint:
        hint = " Ensure logs are ingested and embedded (see README: JOURNAL_INGEST, embeddings)."
    backlog = ""
    if embed_pending_in_window > 0:
        backlog = (
            f" There {'is' if embed_pending_in_window == 1 else 'are'} {embed_pending_in_window} "
            "log row(s) in this time window still waiting for embeddings — similarity search stays empty until "
            "the embed worker catches up."
        )
    return f"No log lines matched the filters in that time window (or nothing embedded yet).{hint}{backlog}"


async def ask_question(question: str, since: str, top_k: int, *, source_scope: str = "all") -> str:
    """Backward-compatible single-shot RAG without intent parsing."""
    rq = ResolvedQuery(
        question=question.strip(),
        since=since,
        top_k=top_k,
        source_scope=source_scope,
        min_level=None,
        source_contains=None,
        include_inventory_context=False,
        is_meta_coverage_question=False,
        journalctl_on_demand=False,
        reboot_journal_focus=False,
        docker_engine_on_demand=False,
        disk_usage_on_demand=False,
        cpu_thermal_on_demand=False,
        gpu_status_on_demand=False,
        use_keyword_supplement=False,
    )
    r = await ask_question_resolved(rq, user_text=question, agent=False, debug=False)
    return r.answer
