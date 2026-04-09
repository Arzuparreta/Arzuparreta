"""Facts about ingestion config and what is stored — for answer grounding (not RAG retrieval)."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import func, not_, select

from db.models import Log
from db.session import session_scope
from logpilot.settings import Settings, get_settings

logger = logging.getLogger(__name__)


def _answer_rules_block(
    _user_text: str,
    counts: dict[str, int],
    settings: Settings,
    *,
    journalctl_excerpt_len: int = 0,
    journalctl_list_boots: bool = False,
    docker_engine_excerpt_len: int = 0,
    disk_usage_excerpt_len: int = 0,
    cpu_thermal_excerpt_len: int = 0,
    gpu_status_excerpt_len: int = 0,
    is_meta_coverage_question: bool = False,
    reboot_journal_focus: bool = False,
    journalctl_on_demand: bool = False,
) -> str:
    """Hard constraints so the model uses inventory facts and does not hallucinate host events."""
    lines: list[str] = []

    if is_meta_coverage_question:
        lines.append(
            "- **Coverage questions:** Start from **embedded row counts by family** and the **ingestion flags** above. "
            "The “Retrieved log lines” section is only a small similarity-based **sample** for illustration — it is **not** "
            "the full set of sources or lines you have. **Do not** present that sample as the main finding (no long recap of "
            "checkpoints, HTTP endpoints, or init sequences from the sample unless framed as one optional example family)."
        )
        lines.append(
            "- **Non-log probes:** This question type **requests** live **Disk usage**, **CPU/thermal**, **GPU status**, and "
            "**Docker Engine** readouts when enabled. Your answer must **acknowledge** those sections (if present in the "
            "prompt) alongside stored logs—not logs alone."
        )

    if reboot_journal_focus:
        jn = counts.get("journal", -1)
        if journalctl_list_boots and journalctl_excerpt_len > 0:
            lines.append(
                "- **Host reboot / systemd:** The prompt includes **`journalctl --list-boots`** for the requested time range. "
                "Count boot table **data rows** as **N**; approximate **reboot events** in the window ≈ **max(0, N − 1)**. "
                "**If N = 1**, say there were **no** *additional* reboots within that window (only the current boot session). "
                "**Do not** infer reboots from **`file:`** lines (e.g. pacman/apt hooks), Docker/DB logs, or **`[GIN]`** HTTP lines "
                "— those are **not** reboot counters."
            )
        elif journalctl_excerpt_len > 0:
            lines.append(
                "- **Host reboot / systemd:** The **Host systemd journal** section is **raw `journalctl` text** from the "
                "machine. It is **not** Logpilot pipeline logs and **not** a description of the `JOURNAL_INGEST` setting. "
                "Answer from those lines literally; do not invent an “ingestion event” schema or confuse them with Docker/DB."
            )
        elif jn == 0:
            lines.append(
                "- **Host reboot count:** With **zero** embedded lines whose `source` starts with `journal:`, you **cannot** "
                "determine how many times the **host machine** rebooted. **Do not** infer reboot counts from Docker container "
                "logs, database logs, or incidental strings (e.g. hook names). Say clearly that the count is **unknown** until "
                "`journal:` data exists (enable `JOURNAL_INGEST`, mount host `/var/log/journal`, embed)."
            )
        elif jn < 0:
            lines.append(
                "- **Host reboot count:** Database counts were unavailable; do not guess reboot numbers from the sample lines alone."
            )

    if docker_engine_excerpt_len > 0:
        lines.append(
            "- **Docker containers:** The **Docker Engine — live read-only inspect** table is authoritative for "
            "`RestartCount`, container state, and `StartedAt`/`FinishedAt`. **`RestartCount` is cumulative since the "
            "container was created** — it is **not** “restarts today” unless the user explicitly accepts that meaning. "
            "Do **not** substitute **`journalctl --list-boots`** for container restart counts."
        )

    if disk_usage_excerpt_len > 0:
        lines.append(
            "- **Disk / filesystem usage:** The **Disk usage** section comes from the read-only **`disk_usage`** probe "
            "(`df`). It is **capacity only** (used/free/% full) — **not** disk I/O load, busy %, throughput, or latency. "
            "Do **not** treat database or application lines about **checkpoints**, **WAL**, or similar as proof the "
            "operator’s whole machine or HDD is I/O-saturated. Do **not** invent capacity numbers from log text when "
            "that section is present; if the probe failed, say disk data was unavailable."
        )

    if cpu_thermal_excerpt_len > 0:
        lines.append(
            "- **CPU load / thermal:** The **CPU load and thermal** section comes from **`cpu_thermal`** "
            "(`/proc/loadavg`, sysfs thermal zones). It reflects **this environment**; VMs/containers may lack thermal "
            "zones. Do **not** invent load or temperature from log text when that section is present."
        )

    if gpu_status_excerpt_len > 0:
        lines.append(
            "- **GPU:** The **GPU status** section comes from **`gpu_status`** (fixed **`nvidia-smi`** CSV and/or "
            "**`rocm-smi`**). Absent drivers or tools → the section explains failure; do **not** invent VRAM or GPU temps "
            "from log text when that section is present."
        )

    if (journalctl_on_demand or reboot_journal_focus) and not lines:
        lines.append(
            "- Ground host/system statements in **journal:** lines when present; if journal count is zero, say systemd-level "
            "facts are missing from stored data."
        )

    if not lines:
        return ""

    return (
        "\n## Internal constraints (assistant only — do not quote in the user reply)\n"
        + "\n".join(lines)
        + "\n*(Apply the rules above silently. In your answer to the user, use plain conversational prose; "
        "do not paste this section or repeat its wording.)*\n"
    )


def _docker_socket_mounted(settings: Settings) -> bool:
    try:
        return Path(settings.docker_socket_path).is_socket()
    except OSError:
        return False


def format_ingestion_settings(settings: Settings) -> str:
    """Human-readable bullets from env (authoritative for what *could* be ingested)."""
    lines: list[str] = [
        f"- Journal ingestion (`JOURNAL_INGEST`): **{'enabled' if settings.journal_ingest else 'disabled'}** — "
        + (
            "when enabled, systemd/journal lines appear as `journal:…` sources."
            if settings.journal_ingest
            else "while disabled, **host systemd events (reboots, units, journald) are not collected** even if Docker logs exist."
        ),
    ]
    jd = (settings.journal_directory or "").strip()
    lines.append(
        f"- Journal directory (`JOURNAL_DIRECTORY`): **{jd or '(default; use host `/var/log/journal` mount in Compose)'}**",
    )
    lines.append(
        f"- Plain-text host logs (`TEXT_LOG_INGEST`): **{'enabled' if settings.text_log_ingest else 'disabled'}** "
        f"(paths under mounted `/var/log`, stored as `file:…` sources).",
    )
    lines.append(
        f"- Docker container JSON logs: reading from **`{settings.docker_log_root}`** (bind-mounted read-only).",
    )
    sock = settings.docker_socket_path
    enrich = settings.docker_enrich_container_names and _docker_socket_mounted(settings)
    lines.append(
        f"- Docker API for names (`DOCKER_ENRICH_CONTAINER_NAMES` + `{sock}`): **{'available' if enrich else 'not available'}** "
        + ("(container names in `docker:…` sources)." if enrich else "(sources stay `docker:<id>`)."),
    )
    dq = settings.docker_query_on_demand and _docker_socket_mounted(settings)
    lines.append(
        f"- Docker Engine live query for `ask` (`DOCKER_QUERY_ON_DEMAND` + socket): **{'enabled' if dq else 'disabled'}** "
        "(read-only `containers/json` + inspect for answers when intent requests it).",
    )
    lines.append(
        f"- Disk usage probe for `ask` (`DISK_USAGE_QUERY_ON_DEMAND`): **{'enabled' if settings.disk_usage_query_on_demand else 'disabled'}** "
        "(read-only `disk_usage` / `df` when intent requests it).",
    )
    lines.append(
        f"- CPU / thermal probe for `ask` (`CPU_THERMAL_QUERY_ON_DEMAND`): **{'enabled' if settings.cpu_thermal_query_on_demand else 'disabled'}** "
        "(read-only `cpu_thermal` — loadavg + sysfs when intent requests it).",
    )
    lines.append(
        f"- GPU status probe for `ask` (`GPU_STATUS_QUERY_ON_DEMAND`): **{'enabled' if settings.gpu_status_query_on_demand else 'disabled'}** "
        "(read-only `gpu_status` — `nvidia-smi` / `rocm-smi` when intent requests it; requires tools in the runtime image).",
    )
    return "\n".join(lines)


async def embedded_row_counts_by_family() -> dict[str, int]:
    """Counts of rows with embeddings, grouped by source prefix family."""
    async with session_scope() as session:
        other_cond = (
            not_(Log.source.startswith("journal:"))
            & not_(Log.source.startswith("docker:"))
            & not_(Log.source.startswith("file:"))
        )
        stmt = (
            select(
                func.count().filter(Log.source.startswith("journal:")).label("journal"),
                func.count().filter(Log.source.startswith("docker:")).label("docker"),
                func.count().filter(Log.source.startswith("file:")).label("file"),
                func.count().filter(other_cond).label("other"),
            )
            .select_from(Log)
            .where(Log.embedding.is_not(None))
        )
        row = (await session.execute(stmt)).one()
    out = {
        "journal": int(row.journal or 0),
        "docker": int(row.docker or 0),
        "file": int(row.file or 0),
        "other": int(row.other or 0),
    }
    return out


async def distinct_embedded_sources_sample(*, limit: int = 50) -> list[str]:
    cap = max(1, min(limit, 200))
    async with session_scope() as session:
        stmt = (
            select(Log.source)
            .where(Log.embedding.is_not(None))
            .distinct()
            .order_by(Log.source.asc())
            .limit(cap)
        )
        raw = (await session.execute(stmt)).scalars().all()
    return [str(s) for s in raw]


async def build_inventory_block_for_prompt(
    user_text: str,
    *,
    journalctl_excerpt_len: int = 0,
    journalctl_list_boots: bool = False,
    docker_engine_excerpt_len: int = 0,
    disk_usage_excerpt_len: int = 0,
    cpu_thermal_excerpt_len: int = 0,
    gpu_status_excerpt_len: int = 0,
    is_meta_coverage_question: bool = False,
    reboot_journal_focus: bool = False,
    journalctl_on_demand: bool = False,
) -> str:
    """Markdown-style block to prepend to the answer prompt when inventory context is needed."""
    settings = get_settings()
    try:
        counts = await embedded_row_counts_by_family()
        samples = await distinct_embedded_sources_sample(limit=45)
    except Exception as exc:
        logger.warning("inventory DB snapshot failed: %s", exc)
        counts = {"journal": -1, "docker": -1, "file": -1, "other": -1}
        samples = []

    settings_block = format_ingestion_settings(settings)
    total_emb = sum(max(0, v) for v in counts.values())
    if counts["journal"] < 0:
        counts_line = "- Embedded rows by family: *(could not query database)*"
    else:
        counts_line = (
            f"- Embedded rows by family: **journal:** {counts['journal']:,}, **docker:** {counts['docker']:,}, "
            f"**file:** {counts['file']:,}, **other:** {counts['other']:,} (total **{total_emb:,}** embedded lines)."
        )

    if counts.get("journal", 0) == 0 and not settings.journal_ingest:
        journal_hint = (
            "\n- **Important:** Journal lines are absent and journal ingestion is off. "
            "Questions about reboots, systemd, or OS-level events usually require **`JOURNAL_INGEST=true`**, "
            "mounting **host `/var/log/journal`** into the container, and waiting for embed."
        )
    elif counts.get("journal", 0) == 0 and settings.journal_ingest:
        journal_hint = (
            "\n- Journal ingestion is enabled but there are no embedded `journal:` rows yet — "
            "check journal mount, permissions, and embed worker."
        )
    else:
        journal_hint = ""

    if journalctl_excerpt_len > 0:
        jdesc = (
            "`journalctl --list-boots`"
            if journalctl_list_boots
            else "`journalctl`"
        )
        journal_hint += (
            f"\n- **Live journalctl for this question:** ~{journalctl_excerpt_len:,} characters were read from {jdesc} "
            "(see **Host systemd journal** in the prompt). This does not require embedded `journal:` rows."
        )

    if docker_engine_excerpt_len > 0:
        journal_hint += (
            f"\n- **Live Docker Engine for this question:** ~{docker_engine_excerpt_len:,} characters from read-only "
            "inspect (see **Docker Engine** section in the prompt). Requires mounted Docker socket and "
            "`DOCKER_QUERY_ON_DEMAND=true`."
        )

    if disk_usage_excerpt_len > 0:
        journal_hint += (
            f"\n- **Disk usage for this question:** ~{disk_usage_excerpt_len:,} characters from the read-only **`disk_usage`** "
            "probe (see **Disk usage** in the prompt). Disable with `DISK_USAGE_QUERY_ON_DEMAND=false` if undesired."
        )

    if cpu_thermal_excerpt_len > 0:
        journal_hint += (
            f"\n- **CPU / thermal for this question:** ~{cpu_thermal_excerpt_len:,} characters from **`cpu_thermal`** "
            "(see **CPU load and thermal** in the prompt). Disable with `CPU_THERMAL_QUERY_ON_DEMAND=false` if undesired."
        )

    if gpu_status_excerpt_len > 0:
        journal_hint += (
            f"\n- **GPU status for this question:** ~{gpu_status_excerpt_len:,} characters from **`gpu_status`** "
            "(see **GPU status** in the prompt). Disable with `GPU_STATUS_QUERY_ON_DEMAND=false` if undesired."
        )

    sample_block = ""
    if samples:
        sample_block = "\nSample distinct `source` values in the database (not exhaustive):\n" + "\n".join(
            f"  - {s}" for s in samples[:40]
        )
    else:
        sample_block = "\nNo embedded log sources found in the database yet."

    rules = _answer_rules_block(
        user_text,
        counts,
        settings,
        journalctl_excerpt_len=journalctl_excerpt_len,
        journalctl_list_boots=journalctl_list_boots,
        docker_engine_excerpt_len=docker_engine_excerpt_len,
        disk_usage_excerpt_len=disk_usage_excerpt_len,
        cpu_thermal_excerpt_len=cpu_thermal_excerpt_len,
        gpu_status_excerpt_len=gpu_status_excerpt_len,
        is_meta_coverage_question=is_meta_coverage_question,
        reboot_journal_focus=reboot_journal_focus,
        journalctl_on_demand=journalctl_on_demand,
    )

    parsed_identity = (
        "\n## Parsed service hints (optional JSONB)\n"
        "- `parsed.service_key` and `parsed.service_label` may be set on **journal:** and **docker:** "
        "rows (e.g. `unit:nginx.service`, `docker:myapp`) for stable filtering and answers.\n"
        "- **file:** plain-text lines **do not** set these in v1 (syslog tag parsing deferred).\n"
    )

    return (
        "## Ingestion configuration (authoritative)\n"
        f"{settings_block}\n\n"
        "## What is actually stored (embedded rows in Postgres)\n"
        f"{counts_line}"
        f"{journal_hint}"
        f"{sample_block}"
        f"{parsed_identity}"
        f"{rules}\n"
    )
