"""Read-only GPU summary via fixed `nvidia-smi` or `rocm-smi` invocations (no shell)."""

from __future__ import annotations

import asyncio
import csv
import hashlib
import io
import json
import logging
import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from tools.contracts import ToolEvidence, ToolFailure, ToolRun

logger = logging.getLogger(__name__)

_NVIDIA_ARGS = (
    "nvidia-smi",
    "--query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.total",
    "--format=csv,noheader,nounits",
)


class GpuStatusParams(BaseModel):
    """Inputs for `gpu_status` (reserved for future filters)."""

    model_config = {"extra": "forbid"}


class GpuDevice(BaseModel):
    index: int | None = None
    name: str
    temperature_c: float | None = None
    utilization_gpu_pct: float | None = None
    memory_used_mib: float | None = None
    memory_total_mib: float | None = None


class GpuStatusResult(BaseModel):
    backend: str = Field(description="nvidia | rocm")
    devices: list[GpuDevice] = Field(default_factory=list)
    rocm_text_excerpt: str | None = None
    collected_at: str
    summary: str


def _fingerprint_args(params: GpuStatusParams) -> str:
    canonical = json.dumps(
        params.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _parse_float_cell(raw: str) -> float | None:
    t = raw.strip()
    if not t or t.lower() in ("[not supported]", "n/a", "err!", "err"):
        return None
    try:
        return float(t)
    except ValueError:
        return None


def _parse_int_cell(raw: str) -> int | None:
    t = raw.strip()
    if not t or not t.lstrip("-").isdigit():
        v = _parse_float_cell(t)
        if v is None:
            return None
        return int(v)
    try:
        return int(t)
    except ValueError:
        return None


def parse_nvidia_smi_csv(text: str) -> list[GpuDevice]:
    """Parse `nvidia-smi --format=csv,noheader,nounits` stdout."""
    devices: list[GpuDevice] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = next(csv.reader(io.StringIO(line)))
        except StopIteration:
            continue
        if len(row) < 6:
            logger.debug("nvidia csv row skipped (short): %s", line[:120])
            continue
        idx_s, name, temp_s, util_s, mem_used_s, mem_tot_s = row[:6]
        name = name.strip()
        if not name:
            continue
        devices.append(
            GpuDevice(
                index=_parse_int_cell(idx_s),
                name=name,
                temperature_c=_parse_float_cell(temp_s),
                utilization_gpu_pct=_parse_float_cell(util_s),
                memory_used_mib=_parse_float_cell(mem_used_s),
                memory_total_mib=_parse_float_cell(mem_tot_s),
            )
        )
    return devices


def _nvidia_summary(devices: list[GpuDevice]) -> str:
    parts: list[str] = []
    for d in devices[:8]:
        seg = d.name
        if d.temperature_c is not None:
            seg += f" {d.temperature_c:.0f}°C"
        if d.utilization_gpu_pct is not None:
            seg += f" util {d.utilization_gpu_pct:.0f}%"
        if d.memory_used_mib is not None and d.memory_total_mib is not None:
            seg += f" VRAM {d.memory_used_mib:.0f}/{d.memory_total_mib:.0f} MiB"
        parts.append(seg)
    tail = f" (+{len(devices) - 8} more)" if len(devices) > 8 else ""
    return "NVIDIA GPUs (nvidia-smi): " + "; ".join(parts) + tail + "."


def _rocm_summary(excerpt: str) -> str:
    first = excerpt.strip().split("\n", 1)[0].strip() if excerpt.strip() else ""
    if first:
        return f"AMD GPUs (rocm-smi excerpt): {first[:200]}"
    return "AMD GPUs: rocm-smi returned no text."


class GpuStatusTool:
    """Allowlisted read-only GPU probe (NVIDIA CSV first, then ROCm text)."""

    name = "gpu_status"
    version = 1
    input_model = GpuStatusParams
    output_model = GpuStatusResult

    async def run(self, params: GpuStatusParams, *, timeout_s: float) -> ToolRun:
        t0 = time.perf_counter()
        fp = _fingerprint_args(params)

        def _done(
            ok: bool,
            output: GpuStatusResult | None,
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

        nvidia_stderr = ""
        try:
            proc = await asyncio.create_subprocess_exec(
                *_NVIDIA_ARGS,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out_b, err_b = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            except TimeoutError:
                try:
                    proc.kill()
                    await proc.wait()
                except ProcessLookupError:
                    pass
                nvidia_stderr = f"nvidia-smi timed out after {timeout_s}s"
            else:
                out_text = out_b.decode("utf-8", errors="replace")
                nvidia_stderr = err_b.decode("utf-8", errors="replace").strip()
                if proc.returncode == 0 and out_text.strip():
                    devices = parse_nvidia_smi_csv(out_text)
                    if devices:
                        collected = datetime.now(timezone.utc).isoformat()
                        result = GpuStatusResult(
                            backend="nvidia",
                            devices=devices,
                            rocm_text_excerpt=None,
                            collected_at=collected,
                            summary=_nvidia_summary(devices),
                        )
                        ser = len(result.model_dump_json().encode("utf-8"))
                        return _done(True, result, None, ser)
        except FileNotFoundError:
            pass

        # ROCm fallback (AMD); still read-only fixed argv.
        try:
            proc2 = await asyncio.create_subprocess_exec(
                "rocm-smi",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            out2_b, _ = await asyncio.wait_for(proc2.communicate(), timeout=timeout_s)
            rocm_text = out2_b.decode("utf-8", errors="replace")
            if proc2.returncode == 0 and rocm_text.strip():
                excerpt = rocm_text.strip()
                if len(excerpt) > 8000:
                    excerpt = excerpt[:8000] + "\n…(truncated)"
                collected = datetime.now(timezone.utc).isoformat()
                result = GpuStatusResult(
                    backend="rocm",
                    devices=[],
                    rocm_text_excerpt=excerpt,
                    collected_at=collected,
                    summary=_rocm_summary(excerpt),
                )
                ser = len(result.model_dump_json().encode("utf-8"))
                return _done(True, result, None, ser)
            rocm_err = rocm_text.strip()[:500] if rocm_text.strip() else "empty stdout"
            return _done(
                False,
                None,
                ToolFailure(
                    code="rocm_error",
                    message="rocm-smi exited non-zero or produced no usable output",
                    details={"stderr_excerpt": rocm_err, "returncode": proc2.returncode},
                ),
                len(out2_b),
            )
        except FileNotFoundError:
            pass
        except TimeoutError:
            try:
                proc2.kill()
                await proc2.wait()
            except (ProcessLookupError, UnboundLocalError):
                pass
            return _done(
                False,
                None,
                ToolFailure(code="timeout", message=f"rocm-smi exceeded {timeout_s}s"),
                0,
            )

        details: dict[str, object] = {}
        if nvidia_stderr:
            details["nvidia_stderr_excerpt"] = nvidia_stderr[:500]
        return _done(
            False,
            None,
            ToolFailure(
                code="not_installed",
                message="Neither nvidia-smi nor rocm-smi produced GPU data in this environment",
                details=details,
            ),
            0,
        )
