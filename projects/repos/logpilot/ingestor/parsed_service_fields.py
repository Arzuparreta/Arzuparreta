"""Optional `service_key` / `service_label` in `Log.parsed` (additive JSONB; no migration)."""

from __future__ import annotations

from typing import Any


def journal_service_key_label(entry: dict[str, Any]) -> tuple[str | None, str | None]:
    """Derive (service_key, service_label) for a journal JSON line; omit both if no stable identity."""
    unit = entry.get("_SYSTEMD_UNIT") or entry.get("UNIT")
    if unit is not None:
        u = str(unit).strip()
        if u:
            return f"unit:{u}", u
    sid = entry.get("SYSLOG_IDENTIFIER")
    if sid is not None:
        s = str(sid).strip()
        if s:
            return f"syslog_id:{s}", s
    comm = entry.get("_COMM")
    if comm is not None:
        c = str(comm).strip()
        if c:
            return f"comm:{c}", c
    return None, None


def docker_service_key_label(resolved_name: str | None, container_id: str) -> tuple[str, str]:
    """Docker identity: named container or docker:<short_id>."""
    if resolved_name and resolved_name.strip():
        n = resolved_name.strip()
        return f"docker:{n}", n
    cid = (container_id or "").strip()
    short = cid[:12] if len(cid) >= 12 else cid
    return f"docker:{short}", short
