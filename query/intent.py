from __future__ import annotations

import errno
import json
import logging
from dataclasses import dataclass

import httpx

from query.levels import normalize_log_level
from query.ollama_chat import ollama_chat
from query.retrieval import normalize_source_contains
from query.since_parse import is_valid_since

logger = logging.getLogger(__name__)

# Long batch runs (e.g. eval) call intent once per question; if Ollama/DNS is down,
# repeating the same WARNING hundreds of times looks like an infinite loop.
_intent_upstream_unreachable_logged = False


def _is_upstream_unreachable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.ConnectError, httpx.TimeoutException)):
        return True
    if isinstance(exc, OSError):
        eno = exc.errno
        if eno in (errno.ECONNREFUSED, errno.EHOSTUNREACH, errno.ENETUNREACH, -2):
            return True
    msg = str(exc).lower()
    return "name or service not known" in msg or "nodename nor servname" in msg

DEFAULT_SINCE = "1h"
DEFAULT_TOP_K = 20
DEFAULT_SOURCE_SCOPE = "all"
TOP_K_MIN = 1
TOP_K_MAX = 200
SOURCE_SCOPES = frozenset({"all", "journal", "docker", "file"})

_INTENT_SYSTEM = """You extract search parameters for a log-analysis tool. The user message is a single request in natural language.

You MUST output exactly one JSON object with ALL of these keys (booleans must be true or false, never omit a key):
- "question": string — the substantive question about the logs. Rephrase clearly; remove redundant time phrases if the window is only given for timing (keep service names, errors, and keywords).
- "since": string — how far back to search logs. Use a relative duration: digits + unit s, m, h, or d (e.g. "15m", "1h", "10d"). **If the user states a specific number** of minutes, hours, or days (e.g. "last 10 days", "in the past 48 hours", "14 days"), set since to **that exact** value ("10d", "48h", "14d"). **Do not** substitute "7d", "this week", or other round numbers when the user gave a different count. Map loose language **only when no explicit number** appears: "last few minutes"→"15m", "last hour"→"1h", "today" or "last 24 hours"→"24h", "yesterday"→"48h", "this week"→"7d", "last month"→"30d". If no time range is implied, use "1h".
- "top_k": integer — how many log lines to retrieve ({min_k}–{max_k}). Use ~20 for normal questions, 10–15 for very narrow "exact line" asks, 40–80 for broad summaries or "everything that happened" style scans. If unspecified, use 20.
- "source_scope": string — which ingested log families to search. One of: "all" (default), "journal" (systemd journal embedded lines only; sources start with journal:), "docker" (container JSON logs only), "file" (host plain-text file logs only; sources start with file:). Use "journal" when the user asks about systemd/units/journald/host services and not containers. Use "docker" when they ask only about containers. Use "file" when they explicitly want syslog-style files under /var/log. If unsure, use "all".
- "min_level": string or null — optional minimum syslog severity (stored levels). One of: emerg, alert, crit, err, warning, notice, info, debug. Map user phrases: "errors only", "only errors", "serious failures" → "err" (include err and more severe). "warnings and above" → "warning". "info and above" / "everything except debug" → "info". Omit or null when severity is not implied.
- "source_contains": string or null — optional substring to match anywhere in the log source path/name (e.g. "nginx", "postgres", "docker:myapp"). Use when the user names a service, container, or unit. Keep it short (one identifier). Omit or null if not implied.
- "include_inventory_context": boolean — true when the answer should include the ingestion inventory preamble (embedded row counts, what is stored, internal guidance). True for: questions about what logs exist, coverage, capabilities, OR host-level topics (reboots, systemd, journal, kernel, shutdown, boot) where grounding in config helps. False for narrow troubleshooting ("nginx 500s in the last hour") unless they also ask about overall access.
- "is_meta_coverage_question": boolean — true only when the user asks what logs sources exist / what you can see / coverage catalog style (not a specific incident). When true, the UI labels the retrieved lines as a small sample, not a full catalog, and the answer step **always requests** live **disk_usage**, **cpu_thermal**, **gpu_status**, and **docker_engine** probes (each is a no-op when off in settings—see ingestion inventory bullets).
- "journalctl_on_demand": boolean — true when live host `journalctl` context would help (**OS / systemd** reboots, journald, kernel, boot/shutdown, or explicit journal questions) and on-demand journal is appropriate. False when only container/file logs matter **unless** the user also asks about the host.
- "reboot_journal_focus": boolean — true only for **host machine (OS)** boot sessions, **host** reboot counts, shutdown, or power cycles — **not** Docker container restarts. For container “reboots” (restarts), uptime, or `RestartCount`, set reboot_journal_focus **false** and docker_engine_on_demand **true**. When true, combine with journalctl_on_demand so the tool prefers `journalctl --list-boots` and related paths.
- "docker_engine_on_demand": boolean — true when read-only **Docker Engine** facts would help: container **restart counts** (`RestartCount`), running/stopped state, **uptime** (`StartedAt`), or a `docker ps`-style overview. True for questions about **containers** restarting, “how many times did my container reboot”, health at the engine level, or which containers exist. **False** for pure application-log troubleshooting with no engine-level status. (Requires Docker socket at runtime and `DOCKER_QUERY_ON_DEMAND` enabled in settings.)
- "disk_usage_on_demand": boolean — true only when read-only **`df`-style capacity** would help: free space, how full a mount is, total size / used / available. **False** for disk **I/O load**, throughput, queue depth, latency, or “is the disk busy / saturated / under heavy load” (including HDD/SSD) — the probe is **`df` only**, not `iostat`. **False** when the question is only about log lines, errors, or services with no capacity angle. (Honored only when `DISK_USAGE_QUERY_ON_DEMAND=true` in settings; probe runs inside the app environment’s mount namespace.)
- "cpu_thermal_on_demand": boolean — true when **CPU load** (`load average`) and/or **thermal** / temperature / overheating questions would help. **False** for pure log or disk questions with no CPU/heat angle. (Honored when `CPU_THERMAL_QUERY_ON_DEMAND=true`; reads `/proc/loadavg` and sysfs thermal zones visible in this environment.)
- "gpu_status_on_demand": boolean — true when **GPU** utilization, VRAM, temperature, or “which GPU / NVIDIA / AMD” questions would help. **False** when the question is only about CPU, disk, or logs with no GPU angle. (Honored when `GPU_STATUS_QUERY_ON_DEMAND=true`; runs fixed **`nvidia-smi`** CSV and/or **`rocm-smi`** — absent binaries → probe reports unavailable; do not invent GPU stats.)
- "use_keyword_supplement": boolean — true when the question is about errors, failures, warnings, crashes, exceptions, denials, or similar troubleshooting where adding keyword-matched lines (ILIKE on common error tokens) in addition to vector search would help. False for pure coverage/meta questions.

Examples:
- "any errors in nginx in the last hour?" → min_level "err", source_contains "nginx", include_inventory_context false, is_meta_coverage_question false, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand false, disk_usage_on_demand false, cpu_thermal_on_demand false, gpu_status_on_demand false, use_keyword_supplement true
- "warnings from sshd in journal today" → source_scope "journal", min_level "warning", source_contains "sshd", include_inventory_context true, journalctl_on_demand true, reboot_journal_focus false, docker_engine_on_demand false, disk_usage_on_demand false, cpu_thermal_on_demand false, gpu_status_on_demand false, use_keyword_supplement true, is_meta_coverage_question false
- "show debug logs for redis" → min_level "debug", source_contains "redis", use_keyword_supplement false, include_inventory_context false, is_meta_coverage_question false, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand false, disk_usage_on_demand false, cpu_thermal_on_demand false, gpu_status_on_demand false
- "what logs do you have access to?" → source_scope "all", include_inventory_context true, is_meta_coverage_question true, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand false, disk_usage_on_demand false, cpu_thermal_on_demand false, gpu_status_on_demand false, use_keyword_supplement false
- "Tell me all the data from my machine that you have access to" → include_inventory_context true, is_meta_coverage_question true, source_scope "all", use_keyword_supplement false (same class as coverage/catalog questions; answer from inventory + constraints, not similarity lines alone)
- "how many times has my computer rebooted in the last 10 days?" → since "10d", include_inventory_context true, journalctl_on_demand true, reboot_journal_focus true, docker_engine_on_demand false, disk_usage_on_demand false, cpu_thermal_on_demand false, gpu_status_on_demand false, use_keyword_supplement false, is_meta_coverage_question false
- "how many times have my Docker containers rebooted today?" → since "24h", source_scope "docker" or "all", include_inventory_context true, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand true, disk_usage_on_demand false, cpu_thermal_on_demand false, gpu_status_on_demand false, use_keyword_supplement false
- "how much free disk space is on /?" → include_inventory_context true, disk_usage_on_demand true, cpu_thermal_on_demand false, gpu_status_on_demand false, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand false, use_keyword_supplement false, is_meta_coverage_question false
- "How full is the root filesystem and should I worry?" → include_inventory_context true, disk_usage_on_demand true, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand false, cpu_thermal_on_demand false, gpu_status_on_demand false, use_keyword_supplement false, is_meta_coverage_question false
- "my computer feels slow — is the HDD under too much load?" → disk_usage_on_demand false (I/O saturation, not capacity); cpu_thermal_on_demand may be true if CPU/heat is relevant; include_inventory_context true, journalctl_on_demand optional, use_keyword_supplement false unless they ask about errors
- "what is the CPU temperature?" → include_inventory_context true, cpu_thermal_on_demand true, gpu_status_on_demand false, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand false, disk_usage_on_demand false, use_keyword_supplement false, is_meta_coverage_question false
- "what is my NVIDIA GPU temperature and memory use?" → include_inventory_context true, gpu_status_on_demand true, cpu_thermal_on_demand false, journalctl_on_demand false, reboot_journal_focus false, docker_engine_on_demand false, disk_usage_on_demand false, use_keyword_supplement false, is_meta_coverage_question false

Respond with ONLY valid JSON. No markdown fences."""


def _first_balanced_json_object(s: str) -> str | None:
    """Return the first top-level `{ ... }` slice, respecting quoted strings (JSON-style)."""
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    i = start
    in_str = False
    escape = False
    while i < len(s):
        c = s[i]
        if in_str:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
        i += 1
    return None


@dataclass(frozen=True)
class ParsedIntent:
    question: str
    since: str
    top_k: int
    source_scope: str
    min_level: str | None
    source_contains: str | None
    include_inventory_context: bool
    is_meta_coverage_question: bool
    journalctl_on_demand: bool
    reboot_journal_focus: bool
    docker_engine_on_demand: bool
    disk_usage_on_demand: bool
    cpu_thermal_on_demand: bool
    gpu_status_on_demand: bool
    use_keyword_supplement: bool


@dataclass(frozen=True)
class ResolvedQuery:
    question: str
    since: str
    top_k: int
    source_scope: str
    min_level: str | None
    source_contains: str | None
    include_inventory_context: bool
    is_meta_coverage_question: bool
    journalctl_on_demand: bool
    reboot_journal_focus: bool
    docker_engine_on_demand: bool
    disk_usage_on_demand: bool
    cpu_thermal_on_demand: bool
    gpu_status_on_demand: bool
    use_keyword_supplement: bool


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if not t.startswith("```"):
        return t
    lines = t.split("\n")
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _parse_intent_json(raw: str) -> dict[str, object]:
    """Parse a single JSON object; tolerate leading/trailing prose and code fences."""
    text = _strip_code_fence(raw)
    candidates: list[str] = []
    if text.strip():
        candidates.append(text.strip())
    for blob in (_first_balanced_json_object(text), _first_balanced_json_object(raw)):
        if blob:
            candidates.append(blob.strip())
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    raise ValueError("no valid JSON object in model output")


def _normalize_since_value(s: str) -> str:
    t = s.strip()
    if is_valid_since(t):
        return t
    logger.warning("invalid since value %r from intent, using %s", s, DEFAULT_SINCE)
    return DEFAULT_SINCE


def _normalize_source_scope(raw: object) -> str:
    if isinstance(raw, str):
        s = raw.strip().lower()
        if s in SOURCE_SCOPES:
            return s
    return DEFAULT_SOURCE_SCOPE


def _coerce_bool(data: dict[str, object], key: str) -> bool:
    """Missing or non-bool values default to False (predictable; prompt requires all keys)."""
    v = data.get(key)
    return v is True


def _coerce_intent(data: dict[str, object], fallback_text: str) -> ParsedIntent:
    q = data.get("question")
    question = q.strip() if isinstance(q, str) and q.strip() else fallback_text.strip()

    s = data.get("since")
    since_raw = s.strip() if isinstance(s, str) and s.strip() else DEFAULT_SINCE
    since = _normalize_since_value(since_raw)

    tk = data.get("top_k")
    top_k = DEFAULT_TOP_K
    if isinstance(tk, int) and not isinstance(tk, bool):
        top_k = max(TOP_K_MIN, min(TOP_K_MAX, tk))
    elif isinstance(tk, float):
        top_k = max(TOP_K_MIN, min(TOP_K_MAX, int(tk)))

    source_scope = _normalize_source_scope(data.get("source_scope"))

    ml = normalize_log_level(data.get("min_level"))
    sc = normalize_source_contains(
        data.get("source_contains") if isinstance(data.get("source_contains"), str) else None,
    )

    return ParsedIntent(
        question=question,
        since=since,
        top_k=top_k,
        source_scope=source_scope,
        min_level=ml,
        source_contains=sc,
        include_inventory_context=_coerce_bool(data, "include_inventory_context"),
        is_meta_coverage_question=_coerce_bool(data, "is_meta_coverage_question"),
        journalctl_on_demand=_coerce_bool(data, "journalctl_on_demand"),
        reboot_journal_focus=_coerce_bool(data, "reboot_journal_focus"),
        docker_engine_on_demand=_coerce_bool(data, "docker_engine_on_demand"),
        disk_usage_on_demand=_coerce_bool(data, "disk_usage_on_demand"),
        cpu_thermal_on_demand=_coerce_bool(data, "cpu_thermal_on_demand"),
        gpu_status_on_demand=_coerce_bool(data, "gpu_status_on_demand"),
        use_keyword_supplement=_coerce_bool(data, "use_keyword_supplement"),
    )


def _default_intent_flags() -> tuple[bool, bool, bool, bool, bool, bool, bool, bool, bool]:
    """Order: inventory, meta, journal, reboot, docker, disk, cpu_thermal, gpu_status, keyword."""
    return (False, False, False, False, False, False, False, False, False)


async def parse_query_intent(user_text: str) -> ParsedIntent:
    """Use the chat model to split time window / retrieval size / source scope from the question."""
    global _intent_upstream_unreachable_logged
    text = user_text.strip()
    inv, meta, jctl, reboot, docker_e, disk_u, cpu_t, gpu_s, kw = _default_intent_flags()
    if not text:
        return ParsedIntent(
            question="",
            since=DEFAULT_SINCE,
            top_k=DEFAULT_TOP_K,
            source_scope=DEFAULT_SOURCE_SCOPE,
            min_level=None,
            source_contains=None,
            include_inventory_context=inv,
            is_meta_coverage_question=meta,
            journalctl_on_demand=jctl,
            reboot_journal_focus=reboot,
            docker_engine_on_demand=docker_e,
            disk_usage_on_demand=disk_u,
            cpu_thermal_on_demand=cpu_t,
            gpu_status_on_demand=gpu_s,
            use_keyword_supplement=kw,
        )

    system = _INTENT_SYSTEM.format(min_k=TOP_K_MIN, max_k=TOP_K_MAX)
    try:
        raw = await ollama_chat(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": text},
            ],
        )
        data = _parse_intent_json(raw)
        return _coerce_intent(data, text)
    except Exception as exc:
        if _is_upstream_unreachable(exc):
            if not _intent_upstream_unreachable_logged:
                _intent_upstream_unreachable_logged = True
                logger.warning(
                    "intent parse failed (Ollama unreachable); using defaults for this process. "
                    "Later failures logged at debug. Original error: %s",
                    exc,
                )
            else:
                logger.debug("intent parse skipped (upstream still unreachable): %s", exc)
        else:
            logger.warning("intent parse failed, using defaults: %s", exc)
        return ParsedIntent(
            question=text,
            since=DEFAULT_SINCE,
            top_k=DEFAULT_TOP_K,
            source_scope=DEFAULT_SOURCE_SCOPE,
            min_level=None,
            source_contains=None,
            include_inventory_context=inv,
            is_meta_coverage_question=meta,
            journalctl_on_demand=jctl,
            reboot_journal_focus=reboot,
            docker_engine_on_demand=docker_e,
            disk_usage_on_demand=disk_u,
            cpu_thermal_on_demand=cpu_t,
            gpu_status_on_demand=gpu_s,
            use_keyword_supplement=kw,
        )


def _strip_or_none(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t if t else None


def _normalize_source_scope_str(s: str | None, fallback: str) -> str:
    if not s or not isinstance(s, str):
        return fallback
    t = s.strip().lower()
    if t in SOURCE_SCOPES:
        return t
    logger.warning("invalid source_scope %r, using %s", s, fallback)
    return fallback


def _inventory_coverage_heuristic(text: str) -> tuple[bool, bool]:
    """When True, (include_inventory_context, is_meta_coverage_question).

    The intent LLM sometimes omits these for paraphrases of "what data/logs do you see / have access to".
    Without the ingestion inventory preamble, the answer step only sees a thin similarity sample and
    mis-describes coverage (e.g. Docker-only). Typo "acess" is normalized.
    """
    t = text.lower().replace("acess", "access")

    catalog = (
        "what logs",
        "which logs",
        "logs do you",
        "logs you have",
        "what log sources",
        "what data",
        "all the data",
        "all data",
        "tell me all",
        "everything you know",
        "everything you have",
        "what you have access",
        "data you have access",
        "what can you see",
        "what do you see",
        "what information do you",
        "what sources",
        "log coverage",
        "data coverage",
        "capabilities",
        "what is ingested",
        "what gets ingested",
        "ingestion settings",
        "where do logs come from",
        "what is stored",
        "what can you help",
        "what else can you",
        "besides logs",
        "not just logs",
        "logpilot can",
        "logpilot search",
        "similarity-retrieved",
        "live read-only probes",
    )
    if any(m in t for m in catalog):
        return (True, True)

    _access_topics = ("data", "log", "machine", "host", "system", "ingest", "stored", "disk", "journal")
    if "have access" in t and any(x in t for x in _access_topics):
        return (True, True)

    return (False, False)


def _meta_coverage_always_on_probes(
    is_meta: bool,
    *,
    disk_usage_on_demand: bool,
    docker_engine_on_demand: bool,
    cpu_thermal_on_demand: bool,
    gpu_status_on_demand: bool,
) -> tuple[bool, bool, bool, bool]:
    """Catalog / coverage asks should pull every read-only live probe the stack allows (settings gate at runtime)."""
    if not is_meta:
        return (
            disk_usage_on_demand,
            docker_engine_on_demand,
            cpu_thermal_on_demand,
            gpu_status_on_demand,
        )
    return (True, True, True, True)


def _disk_capacity_question_heuristic(text: str) -> bool:
    """True when df-style capacity context clearly helps (intent JSON sometimes omits disk_usage_on_demand)."""
    t = text.lower()
    if "how full" in t:
        return True
    if "running out of space" in t:
        return True
    if "out of space" in t and "memory" not in t and "ram" not in t:
        return True
    if "free space" in t and any(x in t for x in ("disk", "drive", "filesystem", "filesystems", "mount", "/")):
        return True
    if "disk space" in t and any(
        x in t for x in ("free", "left", "remain", "running out", "full", "low")
    ):
        return True
    return False


async def resolve_query_params(
    user_text: str,
    since_override: str | None,
    top_k_override: int | None,
    *,
    source_scope_override: str | None = None,
    min_level_override: str | None = None,
    source_contains_override: str | None = None,
    use_intent: bool = True,
) -> ResolvedQuery:
    """Merge explicit overrides with model-parsed intent."""
    inv_d, meta_d, jctl_d, reboot_d, docker_d, disk_d, cpu_d, gpu_d, kw_d = _default_intent_flags()
    if not use_intent:
        q = user_text.strip()
        s_raw = _strip_or_none(since_override) or DEFAULT_SINCE
        s = _normalize_since_value(s_raw)
        k = top_k_override if top_k_override is not None else DEFAULT_TOP_K
        k = max(TOP_K_MIN, min(TOP_K_MAX, k))
        scope = _normalize_source_scope_str(
            _strip_or_none(source_scope_override),
            DEFAULT_SOURCE_SCOPE,
        )
        ml = normalize_log_level(min_level_override) if min_level_override is not None else None
        if min_level_override is not None and ml is None:
            logger.warning("invalid min_level %r ignored", min_level_override)
        sc = normalize_source_contains(source_contains_override)
        inv_h, meta_h = _inventory_coverage_heuristic(q)
        is_meta = meta_d or meta_h
        disk_u = disk_d or _disk_capacity_question_heuristic(q)
        docker_e, cpu_t, gpu_s = docker_d, cpu_d, gpu_d
        disk_u, docker_e, cpu_t, gpu_s = _meta_coverage_always_on_probes(
            is_meta,
            disk_usage_on_demand=disk_u,
            docker_engine_on_demand=docker_e,
            cpu_thermal_on_demand=cpu_t,
            gpu_status_on_demand=gpu_s,
        )
        if is_meta and top_k_override is None:
            k = min(max(k, 12), 20)
        return ResolvedQuery(
            question=q,
            since=s,
            top_k=k,
            source_scope=scope,
            min_level=ml,
            source_contains=sc,
            include_inventory_context=inv_d or inv_h,
            is_meta_coverage_question=is_meta,
            journalctl_on_demand=jctl_d,
            reboot_journal_focus=reboot_d,
            docker_engine_on_demand=docker_e,
            disk_usage_on_demand=disk_u,
            cpu_thermal_on_demand=cpu_t,
            gpu_status_on_demand=gpu_s,
            use_keyword_supplement=False if is_meta else kw_d,
        )

    intent = await parse_query_intent(user_text)
    s_raw = _strip_or_none(since_override) or intent.since
    s = _normalize_since_value(s_raw)
    k = top_k_override if top_k_override is not None else intent.top_k
    k = max(TOP_K_MIN, min(TOP_K_MAX, k))
    scope_raw = _strip_or_none(source_scope_override)
    scope = _normalize_source_scope_str(scope_raw, intent.source_scope)

    if min_level_override is not None:
        ml = normalize_log_level(min_level_override)
        if ml is None:
            logger.warning("invalid min_level %r, using intent", min_level_override)
            ml = intent.min_level
    else:
        ml = intent.min_level

    sc_raw = _strip_or_none(source_contains_override)
    sc = sc_raw if sc_raw is not None else intent.source_contains
    sc = normalize_source_contains(sc)

    disk_u = intent.disk_usage_on_demand or _disk_capacity_question_heuristic(user_text)

    inv_h, meta_h = _inventory_coverage_heuristic(user_text)
    include_inv = intent.include_inventory_context or inv_h
    is_meta = intent.is_meta_coverage_question or meta_h
    # Catalog / coverage questions should not merge error-keyword rows into the sample.
    use_kw = False if is_meta else intent.use_keyword_supplement
    # Broad "what do you have" scans benefit from a larger similarity cap when not overridden.
    # Enough lines to illustrate a family; a large sample makes models ignore inventory + probes.
    if is_meta and top_k_override is None:
        k = min(max(k, 12), 20)

    disk_u, docker_e, cpu_t, gpu_s = _meta_coverage_always_on_probes(
        is_meta,
        disk_usage_on_demand=disk_u,
        docker_engine_on_demand=intent.docker_engine_on_demand,
        cpu_thermal_on_demand=intent.cpu_thermal_on_demand,
        gpu_status_on_demand=intent.gpu_status_on_demand,
    )

    return ResolvedQuery(
        question=intent.question,
        since=s,
        top_k=k,
        source_scope=scope,
        min_level=ml,
        source_contains=sc,
        include_inventory_context=include_inv,
        is_meta_coverage_question=is_meta,
        journalctl_on_demand=intent.journalctl_on_demand,
        reboot_journal_focus=intent.reboot_journal_focus,
        docker_engine_on_demand=docker_e,
        disk_usage_on_demand=disk_u,
        cpu_thermal_on_demand=cpu_t,
        gpu_status_on_demand=gpu_s,
        use_keyword_supplement=use_kw,
    )
