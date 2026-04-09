"""Read-only host service snapshot for `ask` when service-status questions need live context."""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass

from logpilot.settings import get_settings

logger = logging.getLogger(__name__)

_MAX_OUT_CHARS = 30_000
_STATUS_TIMEOUT_S = 8.0
_LIST_TIMEOUT_S = 8.0


@dataclass(frozen=True)
class HostServicesProbeResult:
    block: str
    chars: int
    summary_line: str | None = None


async def _run_cmd(*args: str, timeout_s: float) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        return 124, "", "timeout"
    return proc.returncode, out_b.decode("utf-8", errors="replace"), err_b.decode("utf-8", errors="replace")


def _normalize_unit_name(token: str) -> str:
    """Single-component names become *.service for D-Bus GetUnit; leave dotted names as-is."""
    t = token.strip()
    if not t or "." in t:
        return t
    return f"{t}.service"


def _candidate_units(source_contains: str | None, question: str) -> list[str]:
    cands: list[str] = []
    key = (source_contains or "").strip()
    if key:
        cands.append(_normalize_unit_name(key))
    q = question.lower()
    klow = key.lower()
    if "samba" in q or klow in {"samba", "smb", "smbd", "nmbd"}:
        cands.extend(["smbd.service", "nmbd.service", "samba.service"])
    dedup: list[str] = []
    for c in cands:
        if c and c not in dedup:
            dedup.append(c)
    return dedup[:8]


def _active_line(text: str) -> str | None:
    for line in text.splitlines():
        if line.strip().startswith("Active:"):
            return line.strip()
    return None


def _systemd_bus_unavailable(text: str) -> bool:
    t = text.lower()
    return (
        "failed to connect to bus" in t
        or "can't operate" in t
        or "not been booted with systemd" in t
        or "system has not been booted with systemd" in t
    )


def _parse_busctl_object_line(stdout: str) -> str | None:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("o ") and line.count('"') >= 2:
            first = line.index('"') + 1
            last = line.rindex('"')
            if first < last:
                return line[first:last]
    return None


def _parse_busctl_string_value(stdout: str) -> str | None:
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("s ") and line.count('"') >= 2:
            first = line.index('"') + 1
            last = line.rindex('"')
            if first < last:
                return line[first:last]
    return None


async def _busctl_get_unit_path(unit: str) -> tuple[str | None, str]:
    """Resolve unit name to systemd D-Bus object path; None if not loaded."""
    rc, out, err = await _run_cmd(
        "busctl",
        "--system",
        "call",
        "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1",
        "org.freedesktop.systemd1.Manager",
        "GetUnit",
        "s",
        unit,
        timeout_s=_STATUS_TIMEOUT_S,
    )
    combined = f"{out}\n{err}".lower()
    cmd_hint = f"busctl --system call … GetUnit {unit!r} (exit={rc})"
    snippet = f"```\n$ {cmd_hint}\n{(out or err).strip()}\n```\n"
    if rc != 0 or "not loaded" in combined:
        return None, snippet
    path = _parse_busctl_object_line(out)
    return (path, snippet) if path else (None, snippet)


async def _busctl_unit_property(unit_path: str, prop: str) -> tuple[str | None, str]:
    rc, out, err = await _run_cmd(
        "busctl",
        "--system",
        "get-property",
        "org.freedesktop.systemd1",
        unit_path,
        "org.freedesktop.systemd1.Unit",
        prop,
        timeout_s=_STATUS_TIMEOUT_S,
    )
    snippet = f"```\n$ busctl --system get-property … {prop} (exit={rc})\n{(out or err).strip()}\n```\n"
    if rc != 0:
        return None, snippet
    return _parse_busctl_string_value(out), snippet


async def _host_services_via_host_dbus(
    *,
    source_contains: str | None,
    question: str,
) -> HostServicesProbeResult:
    """When `systemctl` refuses the container, `busctl --system` can still reach the host systemd."""
    intro = (
        "\n\n## Host services snapshot — host systemd via D-Bus (`busctl`)\n\n"
        "This runtime is not PID 1 systemd, but the **host** system bus is reachable. "
        "Read-only `busctl --system` queries `org.freedesktop.systemd1` for unit state "
        "(requires mounting `/run/dbus/system_bus_socket` from the host — see `docker-compose.yml`).\n\n"
    )
    statuses: list[str] = []
    summary_parts: list[str] = []
    for unit in _candidate_units(source_contains, question):
        path, get_snip = await _busctl_get_unit_path(unit)
        statuses.append(f"### `{unit}`\n\n{get_snip}")
        if not path:
            summary_parts.append(f"{unit}: not loaded")
            continue
        ast, ast_snip = await _busctl_unit_property(path, "ActiveState")
        sub, sub_snip = await _busctl_unit_property(path, "SubState")
        statuses.extend([ast_snip, sub_snip])
        if ast and sub:
            summary_parts.append(f"{unit}: ActiveState={ast}, SubState={sub}")
        elif ast:
            summary_parts.append(f"{unit}: ActiveState={ast}")
        else:
            summary_parts.append(f"{unit}: D-Bus path resolved; property read failed (see blocks)")

    block = intro + "\n".join(statuses)
    if len(block) > _MAX_OUT_CHARS:
        block = block[:_MAX_OUT_CHARS] + "\n… [truncated]\n"
    summary = "; ".join(summary_parts) if summary_parts else None
    logger.info("host services on-demand via busctl: chars=%d targets=%d", len(block), len(summary_parts))
    return HostServicesProbeResult(block=block, chars=len(block), summary_line=summary)


async def _active_summary_for_unit(
    unit: str,
    *,
    status_out: str,
    status_err: str,
) -> str | None:
    """Prefer `systemctl status` Active: line; fall back to `systemctl show` (some environments split streams)."""
    combined = f"{status_out}\n{status_err}"
    if _systemd_bus_unavailable(combined):
        return None
    active = _active_line(combined)
    if active:
        return active
    rc, show_out, _ = await _run_cmd(
        "systemctl",
        "show",
        unit,
        "-p",
        "ActiveState",
        "-p",
        "SubState",
        "--no-pager",
        timeout_s=_STATUS_TIMEOUT_S,
    )
    if rc != 0:
        return None
    state: dict[str, str] = {}
    for line in show_out.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            state[k.strip()] = v.strip()
    ast = state.get("ActiveState")
    sub = state.get("SubState")
    if not ast:
        return None
    if sub:
        return f"ActiveState={ast}, SubState={sub}"
    return f"ActiveState={ast}"


async def append_host_services_for_query(
    *,
    enable: bool,
    source_contains: str | None,
    question: str,
) -> HostServicesProbeResult:
    if not enable:
        return HostServicesProbeResult(block="", chars=0, summary_line=None)
    s = get_settings()
    if not s.host_services_query_on_demand:
        return HostServicesProbeResult(block="", chars=0, summary_line=None)
    if shutil.which("systemctl") is None:
        block = (
            "\n\n## Host services snapshot — read-only `systemctl`\n\n"
            "systemctl is not available in this runtime. Do not invent service status.\n"
        )
        return HostServicesProbeResult(block=block, chars=len(block), summary_line="systemctl unavailable in runtime")

    list_rc, list_out, list_err = await _run_cmd(
        "systemctl",
        "list-units",
        "--type=service",
        "--all",
        "--no-pager",
        "--no-legend",
        timeout_s=_LIST_TIMEOUT_S,
    )
    list_combined = f"{list_out}\n{list_err}"
    if _systemd_bus_unavailable(list_combined):
        if shutil.which("busctl"):
            try:
                return await _host_services_via_host_dbus(
                    source_contains=source_contains,
                    question=question,
                )
            except Exception:
                logger.exception("host services busctl path failed; falling back to static error block")
        msg = (
            "systemd is not usable in this runtime (no D-Bus / container is not PID 1 systemd). "
            "Mount the host `/run/dbus/system_bus_socket` into the container (see `docker-compose.yml`) "
            "and ensure `busctl` is available, or use ingested logs / host-side `logpilot ask`."
        )
        snippet = list_combined.strip()
        if len(snippet) > 1200:
            snippet = snippet[:1200] + "\n… [truncated]\n"
        block = (
            "\n\n## Host services snapshot — read-only `systemctl`\n\n"
            f"{msg}\n\n```\n{snippet}\n```\n"
        )
        return HostServicesProbeResult(block=block, chars=len(block), summary_line=msg)

    units_overview = (list_out or list_err).strip()
    if len(units_overview) > _MAX_OUT_CHARS:
        units_overview = units_overview[:_MAX_OUT_CHARS] + "\n… [truncated]\n"

    statuses: list[str] = []
    summary_parts: list[str] = []
    for unit in _candidate_units(source_contains, question):
        rc, out, err = await _run_cmd(
            "systemctl",
            "status",
            unit,
            "--no-pager",
            "--lines=30",
            timeout_s=_STATUS_TIMEOUT_S,
        )
        text = (out or err).strip()
        if len(text) > 2500:
            text = text[:2500] + "\n… [truncated]\n"
        statuses.append(f"### `{unit}` (exit={rc})\n\n```\n{text}\n```\n")
        if "could not be found" in text.lower() or "not-found" in text.lower():
            summary_parts.append(f"{unit}: not found")
        else:
            summary = await _active_summary_for_unit(unit, status_out=out, status_err=err)
            if summary:
                summary_parts.append(f"{unit}: {summary}")
            elif text:
                summary_parts.append(f"{unit}: status output present (see snapshot; no ActiveState line parsed)")

    block = (
        "\n\n## Host services snapshot — read-only `systemctl`\n\n"
        "Live read-only service evidence from `systemctl`. Use this for native service status; "
        "do not infer service health from unrelated app logs.\n\n"
        f"### `systemctl list-units --type=service` (exit={list_rc})\n\n"
        "```\n"
        f"{units_overview}\n"
        "```\n"
    )
    if statuses:
        block += "\n".join(statuses)
    summary = "; ".join(summary_parts) if summary_parts else None
    logger.info("host services on-demand ok: chars=%d targets=%d", len(block), len(statuses))
    return HostServicesProbeResult(block=block, chars=len(block), summary_line=summary)
