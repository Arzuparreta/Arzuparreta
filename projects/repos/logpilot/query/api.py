from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

from query.rag import ask_question_from_prompt

app = FastAPI(title="logpilot", version="0.1.0")


class QueryBody(BaseModel):
    question: str = Field(min_length=1)
    since: str | None = Field(
        default=None,
        description="Optional; if omitted, inferred from the question or defaults to 1h",
    )
    top_k: int | None = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional; if omitted, inferred from the question or defaults to 20",
    )
    use_intent: bool = Field(
        default=True,
        description=(
            "If true, one LLM call extracts question, time window, top_k, source_scope, min_level, "
            "source_contains, and booleans (inventory preamble, meta-coverage label, on-demand journalctl, "
            "reboot-focused journal, Docker engine live inspect, on-demand disk_usage, cpu_thermal, and gpu_status probes, "
            "keyword supplement). "
            "If false, use raw question text and flags default to false except scalar CLI/body overrides."
        ),
    )
    source_scope: Literal["all", "journal", "docker", "file"] | None = Field(
        default=None,
        description="Optional; overrides intent when set. Restricts retrieval to one log family.",
    )
    min_level: str | None = Field(
        default=None,
        description="Optional syslog severity floor: emerg…debug; overrides intent when set",
    )
    source_contains: str | None = Field(
        default=None,
        description="Optional substring match on log source (bounded); overrides intent when set",
    )
    agent: bool = Field(
        default=False,
        description="If true, run bounded multi-step retrieval (constrained JSON planner)",
    )
    include_answer_prompt: bool = Field(
        default=False,
        description=(
            "If true, include `answer_prompt` in the response: the full RAG user message sent to the chat model "
            "(large). For eval dataset export / supervised fine-tuning pipelines."
        ),
    )


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/query")
async def query_logs(
    body: QueryBody,
    debug: bool = Query(False, description="Include retrieval trace (steps, timings) in the response"),
) -> dict[str, object]:
    result = await ask_question_from_prompt(
        body.question,
        since=body.since,
        top_k=body.top_k,
        source_scope=body.source_scope,
        min_level=body.min_level,
        source_contains=body.source_contains,
        use_intent=body.use_intent,
        agent=body.agent,
        debug=debug,
    )
    out: dict[str, object] = {"answer": result.answer}
    if debug and result.trace is not None:
        out["trace"] = result.trace
    if body.include_answer_prompt and result.answer_prompt is not None:
        out["answer_prompt"] = result.answer_prompt
    return out
