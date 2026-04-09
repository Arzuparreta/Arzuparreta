from __future__ import annotations

from typing import Any

import httpx

from logpilot.settings import get_settings


async def ollama_chat(messages: list[dict[str, Any]]) -> str:
    """Single non-streaming chat completion; returns assistant message content."""
    s = get_settings()
    async with httpx.AsyncClient(
        base_url=s.ollama_base_url.rstrip("/"),
        timeout=httpx.Timeout(300.0),
    ) as client:
        r = await client.post(
            "/api/chat",
            json={
                "model": s.chat_model,
                "messages": messages,
                "stream": False,
            },
        )
        r.raise_for_status()
        data = r.json()
        msg = data.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, str):
            raise RuntimeError("unexpected ollama chat response")
        return content
