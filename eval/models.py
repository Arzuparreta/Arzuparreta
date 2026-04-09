from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SuiteItem:
    """One eval prompt with optional query overrides."""

    id: str
    question: str
    tags: tuple[str, ...] = ()
    since: str | None = None
    top_k: int | None = None
    source_scope: str | None = None
    min_level: str | None = None
    source_contains: str | None = None
    use_intent: bool = True
    agent: bool = False


@dataclass
class TrialRecord:
    """Single question × repetition outcome."""

    item_id: str
    repeat_index: int
    question: str
    answer: str
    duration_ms: float
    error: str | None = None
    trace: list[dict[str, Any]] | None = None
    #: Full RAG user message sent to the chat model when eval used ``--save-prompt``.
    answer_prompt: str | None = None
