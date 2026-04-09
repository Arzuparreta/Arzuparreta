"""Single module for candidate log retrieval (vector + optional keyword supplement)."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, not_, or_, select

from db.models import Log
from db.session import session_scope
from embedder.providers import get_embedding_provider
from query.levels import allowed_levels_at_or_above_severity
from query.since_parse import parse_since

logger = logging.getLogger(__name__)

SOURCE_CONTAINS_MAX_LEN = 128

# Keyword supplement when the question sounds like troubleshooting
_ERRORISH = (
    "%error%",
    "%fail%",
    "%warning%",
    "%fatal%",
    "%critical%",
    "%exception%",
    "%traceback%",
    "%(EE)%",
    "%(WW)%",
    "%denied%",
    "%refused%",
)

_SUPPLEMENT_HINTS = (
    "error",
    "fail",
    "warning",
    "problem",
    "issue",
    "wrong",
    "broken",
    "crash",
    "exception",
    "fatal",
    "denied",
    "refused",
    "traceback",
    "trouble",
    "malfunction",
)


def _escape_ilike_pattern(fragment: str) -> str:
    """Escape `%`, `_`, `\\` for use with ILIKE … ESCAPE '\\'."""
    return (
        fragment.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def normalize_source_contains(raw: str | None) -> str | None:
    if raw is None:
        return None
    t = raw.strip()
    if not t:
        return None
    return t[:SOURCE_CONTAINS_MAX_LEN]


def source_ilike_clause(raw: str | None):
    """Bounded substring match on `Log.source` (index may still seq-scan; bounded size)."""
    norm = normalize_source_contains(raw)
    if not norm:
        return None
    pattern = f"%{_escape_ilike_pattern(norm)}%"
    return Log.source.ilike(pattern, escape="\\")


@dataclass(frozen=True)
class SearchParams:
    """Validated retrieval parameters (Phase 1 intent + scopes)."""

    since: str
    top_k: int
    source_scope: str = "all"
    min_level: str | None = None
    source_contains: str | None = None


def _scope_where(source_scope: str):
    if source_scope == "journal":
        return Log.source.startswith("journal:")
    if source_scope == "docker":
        return Log.source.startswith("docker:")
    if source_scope == "file":
        return Log.source.startswith("file:")
    return None


def build_retrieval_where(
    since_dt: datetime,
    *,
    source_scope: str,
    min_level: str | None,
    source_contains: str | None,
    require_embedding: bool = True,
) -> tuple[object, dict[str, object]]:
    """Return SQLAlchemy boolean expression and a dict of filter summary for logging/tests."""
    parts: list[object] = [Log.timestamp >= since_dt]
    if require_embedding:
        parts.append(Log.embedding.is_not(None))
    summary: dict[str, object] = {
        "since_cutoff": since_dt.isoformat(),
        "source_scope": source_scope,
        "min_level": min_level,
        "source_contains": normalize_source_contains(source_contains),
        "require_embedding": require_embedding,
    }

    sw = _scope_where(source_scope)
    if sw is not None:
        parts.append(sw)

    if min_level:
        allowed = allowed_levels_at_or_above_severity(min_level)
        parts.append(Log.level.in_(allowed))

    sc = source_ilike_clause(source_contains)
    if sc is not None:
        parts.append(sc)

    return and_(*parts), summary


def _question_wants_error_supplement(question: str) -> bool:
    q = question.lower()
    return any(h in q for h in _SUPPLEMENT_HINTS)


def _exclude_logpilot_http_access_noise(question: str) -> object | None:
    """Keep unembedded fallback rows from drowning in this app's own Gin access logs."""
    q = question.lower()
    if any(
        x in q
        for x in (
            "embedding",
            "embed worker",
            "logpilot",
            "ollama",
            "/api/chat",
            "api/chat",
        )
    ):
        return None
    return not_(
        and_(
            Log.raw.ilike("%/api/embeddings%"),
            Log.raw.ilike("%GIN%"),
        ),
    )


def _and_optional_noise(base: object, question: str) -> object:
    noise = _exclude_logpilot_http_access_noise(question)
    if noise is None:
        return base
    return and_(base, noise)


@dataclass
class SearchLogsResult:
    rows: list[Log]
    duration_ms: float
    filter_summary: dict[str, object]


async def search_logs(
    question: str,
    params: SearchParams,
    *,
    keyword_supplement: bool | None = None,
) -> SearchLogsResult:
    """
    Embed `question`, run pgvector similarity search, optionally merge keyword supplement rows.
    Applies `min_level` and `source_contains` on both paths.
    """
    since_dt = parse_since(params.since)
    base_where, filter_summary = build_retrieval_where(
        since_dt,
        source_scope=params.source_scope,
        min_level=params.min_level,
        source_contains=params.source_contains,
    )

    want_kw = keyword_supplement if keyword_supplement is not None else _question_wants_error_supplement(question)

    t0 = time.perf_counter()
    provider = await get_embedding_provider()
    qvecs = await provider.embed_many([question])
    qvec = qvecs[0]

    async with session_scope() as session:
        vec_stmt = (
            select(Log)
            .where(base_where)
            .order_by(Log.embedding.cosine_distance(qvec))
            .limit(params.top_k)
        )
        vec_rows = (await session.execute(vec_stmt)).scalars().all()
        rows: list[Log] = list(vec_rows)

        if want_kw:
            seen = {r.id for r in vec_rows}
            supplement_limit = min(params.top_k, 32)
            kw_clause = or_(*[Log.raw.ilike(p) for p in _ERRORISH])
            sup_where = and_(base_where, kw_clause)
            sup_stmt = (
                select(Log)
                .where(sup_where)
                .order_by(Log.timestamp.desc())
                .limit(supplement_limit * 2)
            )
            if seen:
                sup_stmt = sup_stmt.where(~Log.id.in_(seen))
            sup_rows = (await session.execute(sup_stmt)).scalars().all()
            extra: list[Log] = []
            for r in sup_rows:
                if r.id in seen:
                    continue
                seen.add(r.id)
                extra.append(r)
                if len(extra) >= supplement_limit:
                    break
            rows = vec_rows + extra

        if not rows:
            fb_where, _ = build_retrieval_where(
                since_dt,
                source_scope=params.source_scope,
                min_level=params.min_level,
                source_contains=params.source_contains,
                require_embedding=False,
            )
            fb_where = _and_optional_noise(fb_where, question)
            fb_stmt = (
                select(Log)
                .where(fb_where)
                .order_by(Log.timestamp.desc())
                .limit(params.top_k)
            )
            fb_vec = (await session.execute(fb_stmt)).scalars().all()
            rows = list(fb_vec)
            if want_kw:
                seen = {r.id for r in rows}
                supplement_limit = min(params.top_k, 32)
                kw_clause = or_(*[Log.raw.ilike(p) for p in _ERRORISH])
                sup_where = _and_optional_noise(and_(fb_where, kw_clause), question)
                sup_stmt = (
                    select(Log)
                    .where(sup_where)
                    .order_by(Log.timestamp.desc())
                    .limit(supplement_limit * 2)
                )
                if seen:
                    sup_stmt = sup_stmt.where(~Log.id.in_(seen))
                sup_rows = (await session.execute(sup_stmt)).scalars().all()
                extra: list[Log] = []
                for r in sup_rows:
                    if r.id in seen:
                        continue
                    seen.add(r.id)
                    extra.append(r)
                    if len(extra) >= supplement_limit:
                        break
                rows = list(fb_vec) + extra

        if not rows and params.min_level:
            fb2_where, _ = build_retrieval_where(
                since_dt,
                source_scope=params.source_scope,
                min_level=None,
                source_contains=params.source_contains,
                require_embedding=False,
            )
            fb2_where = _and_optional_noise(fb2_where, question)
            fb2_stmt = (
                select(Log)
                .where(fb2_where)
                .order_by(Log.timestamp.desc())
                .limit(params.top_k)
            )
            fb2_vec = (await session.execute(fb2_stmt)).scalars().all()
            rows = list(fb2_vec)
            if want_kw:
                seen2 = {r.id for r in rows}
                supplement_limit = min(params.top_k, 32)
                kw_clause = or_(*[Log.raw.ilike(p) for p in _ERRORISH])
                sup_where2 = _and_optional_noise(and_(fb2_where, kw_clause), question)
                sup_stmt2 = (
                    select(Log)
                    .where(sup_where2)
                    .order_by(Log.timestamp.desc())
                    .limit(supplement_limit * 2)
                )
                if seen2:
                    sup_stmt2 = sup_stmt2.where(~Log.id.in_(seen2))
                sup_rows2 = (await session.execute(sup_stmt2)).scalars().all()
                extra2: list[Log] = []
                for r in sup_rows2:
                    if r.id in seen2:
                        continue
                    seen2.add(r.id)
                    extra2.append(r)
                    if len(extra2) >= supplement_limit:
                        break
                rows = list(fb2_vec) + extra2

        rows = sorted(rows, key=lambda x: x.timestamp)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    logger.info(
        "retrieval search_logs since=%s source_scope=%s min_level=%s source_contains=%r row_count=%d duration_ms=%.1f",
        params.since,
        params.source_scope,
        params.min_level,
        filter_summary.get("source_contains"),
        len(rows),
        elapsed_ms,
    )

    return SearchLogsResult(rows=rows, duration_ms=elapsed_ms, filter_summary=filter_summary)


async def list_distinct_sources(
    params: SearchParams,
    *,
    limit: int = 50,
) -> tuple[list[str], float]:
    """Return distinct `source` values in the time/source scope (capped)."""
    since_dt = parse_since(params.since)
    base_where, _ = build_retrieval_where(
        since_dt,
        source_scope=params.source_scope,
        min_level=params.min_level,
        source_contains=params.source_contains,
    )
    cap = max(1, min(limit, 200))
    t0 = time.perf_counter()
    async with session_scope() as session:
        stmt = select(Log.source).where(base_where).distinct().order_by(Log.source.asc()).limit(cap)
        raw = (await session.execute(stmt)).scalars().all()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    out = [str(s) for s in raw]
    logger.info(
        "retrieval list_distinct_sources since=%s source_scope=%s count=%d duration_ms=%.1f",
        params.since,
        params.source_scope,
        len(out),
        elapsed_ms,
    )
    return out, elapsed_ms
