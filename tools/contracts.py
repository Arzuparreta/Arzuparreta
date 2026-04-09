"""Shared types for read-only tools (evidence + failures)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ToolFailure(BaseModel):
    """Non-exception failure: safe for logs and orchestration (no secrets)."""

    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolEvidence(BaseModel):
    """Summary for traces / future citation UI."""

    tool_name: str
    input_fingerprint: str
    ok: bool
    duration_ms: float
    output_bytes: int
    failure: ToolFailure | None = None


class ToolRun(BaseModel):
    """Single invocation result."""

    evidence: ToolEvidence
    output: BaseModel | None = None
