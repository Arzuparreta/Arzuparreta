"""Read-only disk usage via `df -B1 -P` (POSIX, stable columns)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from tools.contracts import ToolEvidence, ToolFailure, ToolRun

logger = logging.getLogger(__name__)

_DF_ROW = re.compile(
    r"^(\S+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+%|-)\s+(.+)$",
)


class DiskUsageParams(BaseModel):
    """Inputs for `disk_usage`."""

    mount_points: list[str] | None = Field(
        default=None,
        description="If set, only include these mount points (exact paths as reported by df).",
    )


class MountInfo(BaseModel):
    source: str
    mountpoint: str
    size_b: int = Field(ge=0)
    used_b: int = Field(ge=0)
    avail_b: int = Field(ge=0)
    use_pct: float | None = None


class DiskUsageResult(BaseModel):
    mounts: list[MountInfo]
    collected_at: str
    summary: str


def _fingerprint_args(params: DiskUsageParams) -> str:
    canonical = json.dumps(
        params.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _parse_use_pct(raw: str) -> float | None:
    if raw == "-" or not raw.endswith("%"):
        return None
    try:
        return float(raw[:-1].strip())
    except ValueError:
        return None


def _parse_df_stdout(text: str, *, mount_filter: set[str] | None) -> list[MountInfo]:
    mounts: list[MountInfo] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("filesystem"):
            continue
        m = _DF_ROW.match(line)
        if not m:
            logger.debug("df line skipped (unparsed): %s", line[:120])
            continue
        source, size_s, used_s, avail_s, pcent, mp = m.groups()
        mountpoint = mp.strip()
        if mount_filter is not None and mountpoint not in mount_filter:
            continue
        try:
            size_b = int(size_s)
            used_b = int(used_s)
            avail_b = int(avail_s)
        except ValueError:
            continue
        mounts.append(
            MountInfo(
                source=source,
                mountpoint=mountpoint,
                size_b=size_b,
                used_b=used_b,
                avail_b=avail_b,
                use_pct=_parse_use_pct(pcent),
            )
        )
    return mounts


def _human_summary(mounts: list[MountInfo], *, max_list: int = 6) -> str:
    if not mounts:
        return "No mounted filesystems reported."
    parts: list[str] = []
    for m in mounts[:max_list]:
        pct = f"{m.use_pct:.0f}%" if m.use_pct is not None else "n/a"
        gb = 1024**3
        used_g = m.used_b / gb
        size_g = m.size_b / gb
        parts.append(f"{m.mountpoint}: {pct} used ({used_g:.1f}/{size_g:.1f} GiB)")
    tail = ""
    if len(mounts) > max_list:
        tail = f"; +{len(mounts) - max_list} more"
    return "Disk usage: " + "; ".join(parts) + tail + "."


class DiskUsageTool:
    """Allowlisted read-only disk usage probe."""

    name = "disk_usage"
    version = 1
    input_model = DiskUsageParams
    output_model = DiskUsageResult

    async def run(self, params: DiskUsageParams, *, timeout_s: float) -> ToolRun:
        t0 = time.perf_counter()
        fp = _fingerprint_args(params)
        mount_filter: set[str] | None = None
        if params.mount_points:
            mount_filter = set()
            for raw in params.mount_points:
                p = raw.strip()
                if p == "/":
                    mount_filter.add("/")
                else:
                    mount_filter.add(p.rstrip("/") or "/")

        def _done(
            ok: bool,
            output: DiskUsageResult | None,
            failure: ToolFailure | None,
            out_bytes: int,
        ) -> ToolRun[DiskUsageResult]:
            dur_ms = (time.perf_counter() - t0) * 1000.0
            return ToolRun(
                evidence=ToolEvidence(
                    tool_name=self.name,
                    input_fingerprint=fp,
                    ok=ok,
                    duration_ms=dur_ms,
                    output_bytes=out_bytes,
                    failure=failure,
                ),
                output=output,
            )

        try:
            proc = await asyncio.create_subprocess_exec(
                "df",
                "-B1",
                "-P",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            return _done(
                False,
                None,
                ToolFailure(
                    code="not_installed",
                    message="df executable not found",
                ),
                0,
            )

        try:
            out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
        except TimeoutError:
            proc.kill()
            await proc.wait()
            return _done(
                False,
                None,
                ToolFailure(code="timeout", message=f"df exceeded {timeout_s}s"),
                0,
            )

        out_text = out_b.decode("utf-8", errors="replace")
        err_text = err_b.decode("utf-8", errors="replace").strip()
        if proc.returncode != 0:
            return _done(
                False,
                None,
                ToolFailure(
                    code="df_error",
                    message="df exited non-zero",
                    details={"stderr": err_text[:500], "returncode": proc.returncode},
                ),
                len(out_b),
            )

        mounts = _parse_df_stdout(out_text, mount_filter=mount_filter)
        if mount_filter and not mounts:
            return _done(
                False,
                None,
                ToolFailure(
                    code="no_match",
                    message="No mounts matched mount_points filter",
                    details={"mount_points": sorted(mount_filter)},
                ),
                len(out_b),
            )

        collected = datetime.now(timezone.utc).isoformat()
        result = DiskUsageResult(
            mounts=mounts,
            collected_at=collected,
            summary=_human_summary(mounts),
        )
        serialized = result.model_dump_json().encode("utf-8")
        return _done(True, result, None, len(serialized))
