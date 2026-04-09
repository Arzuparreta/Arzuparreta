from __future__ import annotations

import asyncio
import logging
from typing import Protocol, runtime_checkable

import httpx

from logpilot.settings import get_settings

logger = logging.getLogger(__name__)


@runtime_checkable
class EmbeddingProvider(Protocol):
    async def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class OllamaEmbeddingProvider:
    def __init__(self) -> None:
        s = get_settings()
        self._model = s.embedding_model
        self._client = httpx.AsyncClient(
            base_url=s.ollama_base_url.rstrip("/"),
            timeout=httpx.Timeout(120.0),
        )

    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            r = await self._client.post(
                "/api/embeddings",
                json={"model": self._model, "prompt": t},
            )
            r.raise_for_status()
            data = r.json()
            emb = data.get("embedding")
            if not isinstance(emb, list):
                raise RuntimeError("ollama embeddings response missing embedding")
            out.append([float(x) for x in emb])
        return out

    async def aclose(self) -> None:
        await self._client.aclose()


_st_model = None


def _load_st_model():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer

        s = get_settings()
        name = s.st_embedding_model or "nomic-ai/nomic-embed-text-v1.5"
        logger.info("loading sentence-transformers model %s", name)
        _st_model = SentenceTransformer(name, trust_remote_code=True)
    return _st_model


class SentenceTransformerEmbeddingProvider:
    async def embed_many(self, texts: list[str]) -> list[list[float]]:
        model = await asyncio.to_thread(_load_st_model)

        def enc() -> list[list[float]]:
            vecs = model.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            t = vecs.tolist()
            if t and isinstance(t[0], float):
                return [t]
            return t

        return await asyncio.to_thread(enc)


_provider: EmbeddingProvider | None = None


async def get_embedding_provider() -> EmbeddingProvider:
    global _provider
    if _provider is not None:
        return _provider

    s = get_settings()
    if s.use_embedding_fallback:
        _provider = SentenceTransformerEmbeddingProvider()
        return _provider

    p = OllamaEmbeddingProvider()
    try:
        r = await p._client.get("/api/tags")
        r.raise_for_status()
    except Exception as exc:
        logger.warning("ollama not reachable (%s), falling back to sentence-transformers", exc)
        await p.aclose()
        try:
            _provider = SentenceTransformerEmbeddingProvider()
            return _provider
        except ImportError as ie:
            logger.error(
                "sentence-transformers is not installed; rebuild with pip install '.[embeddings-local]' "
                "or ensure Ollama is reachable."
            )
            raise ie from exc

    _provider = p
    return _provider
