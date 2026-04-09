from __future__ import annotations

import asyncio
import logging

import typer

from logpilot.settings import get_settings
import json

from eval.cli import eval_app
from query.rag import ask_question_from_prompt

app = typer.Typer(help="logpilot — local log intelligence", no_args_is_help=True)
app.add_typer(eval_app, name="eval")

probe_app = typer.Typer(help="Read-only host probes (allowlisted tools; see docs/plans/local-sysadmin-copilot-roadmap.md)")
app.add_typer(probe_app, name="probe")


def _configure_cli_logging() -> None:
    """INFO for app; keep httpx/httpcore quiet so one-shot commands stay readable."""
    s = get_settings()
    logging.basicConfig(level=getattr(logging, s.log_level.upper(), logging.INFO))
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


@app.command()
def run() -> None:
    """Run ingest + embed loops and optional API server."""

    s = get_settings()
    logging.basicConfig(level=getattr(logging, s.log_level.upper(), logging.INFO))

    from logpilot.main import run_services

    asyncio.run(run_services())


@app.command()
def version() -> None:
    """Print the installed package version."""

    from importlib.metadata import version

    typer.echo(version("logpilot"))


@app.command()
def doctor(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Include ingestion DB stats (24h row counts by family, pending embeddings)",
    ),
) -> None:
    """Check database, Ollama, and ingestion environment (for troubleshooting)."""

    _configure_cli_logging()

    from query.doctor import run_doctor

    code = asyncio.run(run_doctor(verbose=verbose))
    raise typer.Exit(code=code)


@app.command()
def ask(
    question: list[str] = typer.Argument(..., help="Natural language question; may include time span and how broad to search"),
    since: str | None = typer.Option(
        None,
        "--since",
        help="Override time window (e.g. 1h, 30m, 7d); if omitted, inferred from the question or 1h",
    ),
    top_k: int | None = typer.Option(
        None,
        "--top-k",
        help="Override how many log lines to retrieve; if omitted, inferred from the question or 20",
    ),
    no_intent: bool = typer.Option(
        False,
        "--no-intent",
        "--raw",
        help=(
            "Skip intent LLM; use full text as the question. Scalar flags use CLI/API only; "
            "inventory / journalctl-on-demand / keyword-supplement default off."
        ),
    ),
    source_scope: str | None = typer.Option(
        None,
        "--source-scope",
        help="Restrict logs: all | journal | docker | file (default all; overrides intent if set)",
    ),
    min_level: str | None = typer.Option(
        None,
        "--min-level",
        help="Minimum syslog severity (emerg…debug); overrides intent if set",
    ),
    source_contains: str | None = typer.Option(
        None,
        "--source-contains",
        help="Substring filter on log source; overrides intent if set",
    ),
    agent: bool = typer.Option(
        False,
        "--agent",
        help=(
            "Multi-step bounded retrieval planner (read-only tools). "
            "On-demand journalctl still runs when intent enables it, same as without --agent."
        ),
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Print retrieval trace JSON after the answer",
    ),
) -> None:
    """Ask a question over recent logs (RAG). Time range and breadth can be expressed in plain language."""

    _configure_cli_logging()

    q = " ".join(question).strip()
    if not q:
        raise typer.Exit(code=1)
    result = asyncio.run(
        ask_question_from_prompt(
            q,
            since=since,
            top_k=top_k,
            source_scope=source_scope,
            min_level=min_level,
            source_contains=source_contains,
            use_intent=not no_intent,
            agent=agent,
            debug=debug,
        ),
    )
    typer.echo(result.answer)
    if debug and result.trace is not None:
        typer.echo(json.dumps(result.trace, indent=2))


@probe_app.command("disk-usage")
def probe_disk_usage(
    mounts: str | None = typer.Option(
        None,
        "--mounts",
        help="Comma-separated mount points to include (default: all filesystems df reports)",
    ),
    timeout_s: float = typer.Option(5.0, "--timeout", help="Hard timeout in seconds"),
    json_out: bool = typer.Option(False, "--json", help="Print full tool JSON (evidence + output)"),
) -> None:
    """Run the read-only disk_usage tool (`df -B1 -P`). Reflects mounts visible inside this environment."""

    _configure_cli_logging()

    from tools.disk_usage import DiskUsageParams, DiskUsageTool

    mount_list: list[str] | None = None
    if mounts and mounts.strip():
        mount_list = [p.strip() for p in mounts.split(",") if p.strip()]

    async def _run() -> int:
        tool = DiskUsageTool()
        run = await tool.run(DiskUsageParams(mount_points=mount_list), timeout_s=timeout_s)
        if json_out:
            typer.echo(run.model_dump_json(indent=2))
            return 0
        ev = run.evidence
        if not ev.ok or run.output is None:
            msg = ev.failure.message if ev.failure else "disk probe failed"
            typer.echo(f"disk_usage: FAIL — {msg}", err=True)
            return 1
        out = run.output
        summary = getattr(out, "summary", str(out))
        typer.echo(summary)
        return 0

    raise typer.Exit(code=asyncio.run(_run()))


@probe_app.command("cpu-thermal")
def probe_cpu_thermal(
    timeout_s: float = typer.Option(3.0, "--timeout", help="Hard timeout in seconds"),
    json_out: bool = typer.Option(False, "--json", help="Print full tool JSON (evidence + output)"),
) -> None:
    """Run the read-only cpu_thermal probe (`/proc/loadavg`, sysfs thermal)."""

    _configure_cli_logging()

    from tools.cpu_thermal import CpuThermalParams, CpuThermalTool

    async def _run() -> int:
        tool = CpuThermalTool()
        run = await tool.run(CpuThermalParams(), timeout_s=timeout_s)
        if json_out:
            typer.echo(run.model_dump_json(indent=2))
            return 0
        ev = run.evidence
        if not ev.ok or run.output is None:
            msg = ev.failure.message if ev.failure else "cpu_thermal probe failed"
            typer.echo(f"cpu_thermal: FAIL — {msg}", err=True)
            return 1
        out = run.output
        summary = getattr(out, "summary", str(out))
        typer.echo(summary)
        return 0

    raise typer.Exit(code=asyncio.run(_run()))


@probe_app.command("gpu-status")
def probe_gpu_status(
    timeout_s: float = typer.Option(8.0, "--timeout", help="Hard timeout in seconds"),
    json_out: bool = typer.Option(False, "--json", help="Print full tool JSON (evidence + output)"),
) -> None:
    """Run the read-only gpu_status probe (nvidia-smi CSV, then rocm-smi if needed)."""

    _configure_cli_logging()

    from tools.gpu_status import GpuStatusParams, GpuStatusTool

    async def _run() -> int:
        tool = GpuStatusTool()
        run = await tool.run(GpuStatusParams(), timeout_s=timeout_s)
        if json_out:
            typer.echo(run.model_dump_json(indent=2))
            return 0
        ev = run.evidence
        if not ev.ok or run.output is None:
            msg = ev.failure.message if ev.failure else "gpu_status probe failed"
            typer.echo(f"gpu_status: FAIL — {msg}", err=True)
            return 1
        out = run.output
        summary = getattr(out, "summary", str(out))
        typer.echo(summary)
        return 0

    raise typer.Exit(code=asyncio.run(_run()))


if __name__ == "__main__":
    app()
