"""Read-only CPU load (`/proc/loadavg`) and thermal zones (sysfs) — best-effort per host."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from tools.contracts import ToolEvidence, ToolFailure, ToolRun

logger = logging.getLogger(__name__)

_PROC_LOADAVG = Path("/proc/loadavg")
_SYS_THERMAL = Path("/sys/class/thermal")
_ZONE_DIR = re.compile(r"^thermal_zone\d+$")


class CpuThermalParams(BaseModel):
    max_thermal_zones: int = Field(default=32, ge=0, le=128)


class LoadAvgSample(BaseModel):
    avg_1m: float
    avg_5m: float
    avg_15m: float
    runnable_entities: int
    scheduling_entities: int
    last_pid: int


class ThermalZoneReading(BaseModel):
    zone_id: str
    type_label: str
    temp_c: float | None = None


class CpuThermalResult(BaseModel):
    logical_cpus: int
    loadavg: LoadAvgSample | None
    thermal_zones: list[ThermalZoneReading]
    collected_at: str
    summary: str


def _fingerprint_args(params: CpuThermalParams) -> str:
    canonical = json.dumps(
        params.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def parse_loadavg_line(text: str) -> LoadAvgSample | None:
    """Parse a single `/proc/loadavg` line."""
    line = text.strip()
    if not line:
        return None
    parts = line.split()
    if len(parts) < 5:
        return None
    try:
        a1, a5, a15 = float(parts[0]), float(parts[1]), float(parts[2])
        run_total = parts[3].split("/")
        if len(run_total) != 2:
            return None
        runnable = int(run_total[0])
        total_sched = int(run_total[1])
        last_pid = int(parts[4])
    except (ValueError, IndexError):
        return None
    return LoadAvgSample(
        avg_1m=a1,
        avg_5m=a5,
        avg_15m=a15,
        runnable_entities=runnable,
        scheduling_entities=total_sched,
        last_pid=last_pid,
    )


def _read_zone(zone_dir: Path) -> ThermalZoneReading | None:
    zid = zone_dir.name
    tpath = zone_dir / "type"
    temp_path = zone_dir / "temp"
    try:
        type_label = tpath.read_text(encoding="utf-8", errors="replace").strip() or zid
    except OSError:
        type_label = zid
    temp_c: float | None = None
    try:
        raw = temp_path.read_text(encoding="utf-8", errors="replace").strip()
        if raw and raw.lstrip("-").isdigit():
            milli = int(raw)
            temp_c = milli / 1000.0
    except OSError:
        pass
    except ValueError:
        pass
    return ThermalZoneReading(zone_id=zid, type_label=type_label, temp_c=temp_c)


def _collect_sync(max_zones: int) -> tuple[int, LoadAvgSample | None, list[ThermalZoneReading]]:
    logical = os.cpu_count() or 0
    load: LoadAvgSample | None = None
    if _PROC_LOADAVG.is_file():
        try:
            load = parse_loadavg_line(_PROC_LOADAVG.read_text(encoding="utf-8", errors="replace"))
        except OSError as exc:
            logger.debug("read /proc/loadavg: %s", exc)

    zones: list[ThermalZoneReading] = []
    cap = max(0, min(max_zones, 128))
    if cap > 0 and _SYS_THERMAL.is_dir():
        try:
            names = sorted(
                p.name for p in _SYS_THERMAL.iterdir() if p.is_dir() and _ZONE_DIR.match(p.name)
            )
        except OSError as exc:
            logger.debug("list thermal: %s", exc)
            names = []
        for name in names[:cap]:
            z = _read_zone(_SYS_THERMAL / name)
            if z is not None:
                zones.append(z)

    return logical, load, zones


def _human_summary(logical: int, load: LoadAvgSample | None, zones: list[ThermalZoneReading]) -> str:
    parts: list[str] = []
    if logical > 0:
        parts.append(f"{logical} logical CPU(s) visible")
    if load is not None:
        parts.append(
            f"load avg {load.avg_1m:.2f} / {load.avg_5m:.2f} / {load.avg_15m:.2f} "
            f"({load.runnable_entities}/{load.scheduling_entities} runnable/total kernel sched entities)",
        )
    if zones:
        temps = [f"{z.type_label}:{z.temp_c:.1f}°C" for z in zones if z.temp_c is not None]
        if temps:
            parts.append("thermal: " + "; ".join(temps[:12]))
            if len(temps) > 12:
                parts.append(f"(+{len(temps) - 12} more zones with temp)")
        else:
            parts.append(f"{len(zones)} thermal zone(s) present (no readable temps)")
    if not parts:
        return "No CPU load or thermal data could be read."
    return "CPU / thermal: " + " — ".join(parts) + "."


class CpuThermalTool:
    """Allowlisted read-only loadavg + sysfs thermal probe."""

    name = "cpu_thermal"
    version = 1
    input_model = CpuThermalParams
    output_model = CpuThermalResult

    async def run(self, params: CpuThermalParams, *, timeout_s: float) -> ToolRun:
        t0 = time.perf_counter()
        fp = _fingerprint_args(params)

        def _done(
            ok: bool,
            output: CpuThermalResult | None,
            failure: ToolFailure | None,
            out_bytes: int,
        ) -> ToolRun:
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
            logical, load, zones = await asyncio.wait_for(
                asyncio.to_thread(_collect_sync, params.max_thermal_zones),
                timeout=timeout_s,
            )
        except TimeoutError:
            return _done(
                False,
                None,
                ToolFailure(code="timeout", message=f"cpu_thermal exceeded {timeout_s}s"),
                0,
            )

        useful = load is not None or bool(zones) or logical > 0
        if not useful:
            return _done(
                False,
                None,
                ToolFailure(
                    code="no_data",
                    message="No loadavg, thermal zones, or CPU count available",
                ),
                0,
            )

        collected = datetime.now(timezone.utc).isoformat()
        result = CpuThermalResult(
            logical_cpus=logical,
            loadavg=load,
            thermal_zones=zones,
            collected_at=collected,
            summary=_human_summary(logical, load, zones),
        )
        out_b = len(result.model_dump_json().encode("utf-8"))
        return _done(True, result, None, out_b)
