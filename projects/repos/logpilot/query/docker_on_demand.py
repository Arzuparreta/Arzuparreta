"""Read-only Docker Engine context for answers (RestartCount, state) — not a substitute for log RAG."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from logpilot.settings import Settings, get_settings

logger = logging.getLogger(__name__)

# Cap prompt size; each inspect is small but many containers add up.
_MAX_BLOCK_CHARS = 100_000
_DEFAULT_MAX_CONTAINERS = 50
_DEFAULT_TIMEOUT_S = 30.0


def _docker_socket_ok(settings: Settings) -> bool:
    try:
        return Path(settings.docker_socket_path).is_socket()
    except OSError:
        return False


def _format_engine_block(lines: list[str]) -> str:
    header = (
        "\n\n## Docker Engine — live read-only inspect (authoritative for container lifecycle)\n\n"
        "Data from **`GET /containers/json`** and **`GET /containers/{id}/json`** on the Docker Unix socket. "
        "This is **not** ingested log text.\n\n"
        "**`RestartCount`:** cumulative restarts **since this container was created**, not “today only” or per arbitrary "
        "calendar window. For restart counts **inside a specific time range**, you would need **`docker events`** "
        "(not implemented here) or correlated log lines.\n\n"
        "**Host reboots** are **not** the same as container restarts — use **`journalctl --list-boots`** (when present) "
        "for OS boot sessions.\n\n"
        "---\n\n"
    )
    body = "\n".join(lines)
    block = header + body
    if len(block) > _MAX_BLOCK_CHARS:
        block = block[:_MAX_BLOCK_CHARS] + "\n… [truncated]\n"
    return block


async def fetch_docker_engine_summary(
    *,
    settings: Settings | None = None,
    max_containers: int = _DEFAULT_MAX_CONTAINERS,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> tuple[str | None, str | None]:
    """
    Return markdown block for the answer prompt, or (None, reason) on skip/failure.
    Only GET endpoints; no container start/stop/exec.
    """
    s = settings or get_settings()
    if not s.docker_query_on_demand:
        return None, "disabled by DOCKER_QUERY_ON_DEMAND=false"

    if not _docker_socket_ok(s):
        return None, f"Docker socket not available at {s.docker_socket_path}"

    cap = max(1, min(max_containers, 200))
    sock = Path(s.docker_socket_path)
    transport = httpx.AsyncHTTPTransport(uds=sock)
    lines: list[str] = [
        "| Name | Container ID | State | RestartCount | StartedAt | FinishedAt |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    n_inspected = 0

    try:
        async with httpx.AsyncClient(transport=transport, timeout=timeout_s) as client:
            r = await client.get("http://localhost/containers/json", params={"all": "true"})
            r.raise_for_status()
            raw_list = r.json()

            if not isinstance(raw_list, list):
                return None, "docker list: unexpected JSON"

            def sort_key(c: dict[str, Any]) -> tuple[str, str]:
                names = c.get("Names") if isinstance(c.get("Names"), list) else []
                n0 = ""
                if names and isinstance(names[0], str):
                    n0 = names[0].lstrip("/")
                cid = c.get("Id") if isinstance(c.get("Id"), str) else ""
                return (n0.lower(), cid)

            containers: list[dict[str, Any]] = [c for c in raw_list if isinstance(c, dict)]
            containers.sort(key=sort_key)

            for c in containers[:cap]:
                cid = c.get("Id")
                if not isinstance(cid, str) or not cid.strip():
                    continue
                try:
                    ir = await client.get(f"http://localhost/containers/{cid}/json")
                    ir.raise_for_status()
                    data = ir.json()
                except (httpx.HTTPError, OSError, ValueError) as exc:
                    logger.info("docker inspect %s… failed: %s", cid[:12], exc)
                    continue

                if not isinstance(data, dict):
                    continue

                name = (data.get("Name") or "").lstrip("/") or "(unnamed)"
                rc = data.get("RestartCount", 0)
                if isinstance(rc, bool) or not isinstance(rc, int):
                    restart = 0
                else:
                    restart = rc
                state = data.get("State") if isinstance(data.get("State"), dict) else {}
                status = state.get("Status") if isinstance(state.get("Status"), str) else ""
                started = state.get("StartedAt") if isinstance(state.get("StartedAt"), str) else ""
                finished = state.get("FinishedAt") if isinstance(state.get("FinishedAt"), str) else ""

                short_id = cid[:12]
                lines.append(
                    f"| {name} | {short_id} | {status} | {restart} | {started} | {finished} |",
                )
                n_inspected += 1
    except (httpx.HTTPError, OSError, ValueError) as exc:
        logger.info("docker engine summary failed: %s", exc)
        return None, f"docker list failed: {exc!s}"[:500]

    if n_inspected == 0:
        return None, "no containers could be inspected"

    logger.info("docker engine summary ok: rows=%d chars≈%d", n_inspected, len("\n".join(lines)))
    return _format_engine_block(lines), None


async def append_docker_engine_for_query(docker_engine_on_demand: bool) -> tuple[str, int]:
    """
    If intent requests Docker engine context and settings allow, fetch inspect table for the prompt.
    Returns (markdown_fragment, raw body length for inventory hints).
    """
    if not docker_engine_on_demand:
        return "", 0
    s = get_settings()
    if not s.docker_query_on_demand:
        return "", 0

    block, err = await fetch_docker_engine_summary(settings=s)
    if err:
        logger.info("docker engine on-demand skipped: %s", err)
    if not block:
        return "", 0
    return block, len(block)
