from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql

from db.models import Log
from query.retrieval import (
    SOURCE_CONTAINS_MAX_LEN,
    build_retrieval_where,
    normalize_source_contains,
    source_ilike_clause,
)
from query import retrieval as retrieval_mod


def _compile_where(expr: object) -> str:
    return str(
        expr.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        ),
    )


def test_normalize_source_contains_trims_and_caps() -> None:
    long = "a" * (SOURCE_CONTAINS_MAX_LEN + 50)
    assert len(normalize_source_contains(long) or "") == SOURCE_CONTAINS_MAX_LEN
    assert normalize_source_contains("  x  ") == "x"
    assert normalize_source_contains("") is None
    assert normalize_source_contains(None) is None


def test_source_ilike_clause_none_when_empty() -> None:
    assert source_ilike_clause("") is None
    assert source_ilike_clause("   ") is None


def test_build_retrieval_where_summary() -> None:
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    expr, summary = build_retrieval_where(
        since,
        source_scope="journal",
        min_level="err",
        source_contains="nginx",
    )
    assert summary["source_scope"] == "journal"
    assert summary["min_level"] == "err"
    assert summary["source_contains"] == "nginx"
    assert "since_cutoff" in summary
    assert expr is not None


def test_exclude_logpilot_noise_not_disabled_by_substrings() -> None:
    """'gin' as a substring (e.g. in 'beginning') must not disable the access-log filter."""
    assert retrieval_mod._exclude_logpilot_http_access_noise("logs at the beginning of the day") is not None
    assert retrieval_mod._exclude_logpilot_http_access_noise("ollama model errors") is None


def test_build_retrieval_where_require_embedding_in_summary() -> None:
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    _, s_default = build_retrieval_where(
        since,
        source_scope="all",
        min_level=None,
        source_contains=None,
    )
    assert s_default["require_embedding"] is True
    _, s_off = build_retrieval_where(
        since,
        source_scope="all",
        min_level=None,
        source_contains=None,
        require_embedding=False,
    )
    assert s_off["require_embedding"] is False


def test_question_wants_error_supplement() -> None:
    assert retrieval_mod._question_wants_error_supplement("why is ssh connection refused")
    assert retrieval_mod._question_wants_error_supplement("nginx traceback")
    assert not retrieval_mod._question_wants_error_supplement("what sources exist")
    assert not retrieval_mod._question_wants_error_supplement("")


def test_and_optional_noise_returns_base_when_filter_disabled() -> None:
    sentinel = object()
    assert retrieval_mod._and_optional_noise(sentinel, "ollama embedding latency") is sentinel


def test_and_optional_noise_wraps_when_filter_enabled() -> None:
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    base = Log.timestamp >= since
    out = retrieval_mod._and_optional_noise(base, "apache error logs")
    assert out is not base


def test_escape_ilike_pattern_escapes_metacharacters() -> None:
    assert retrieval_mod._escape_ilike_pattern("100%") == "100\\%"
    assert retrieval_mod._escape_ilike_pattern("a_b") == "a\\_b"
    assert retrieval_mod._escape_ilike_pattern("\\") == "\\\\"
    assert retrieval_mod._escape_ilike_pattern("%_\\") == "\\%\\_\\\\"


def test_exclude_logpilot_noise_disabled_for_in_app_topics() -> None:
    assert retrieval_mod._exclude_logpilot_http_access_noise("logpilot API errors") is None
    assert retrieval_mod._exclude_logpilot_http_access_noise("embed worker backlog") is None
    assert retrieval_mod._exclude_logpilot_http_access_noise("POST /api/chat failures") is None
    assert retrieval_mod._exclude_logpilot_http_access_noise("kernel oops") is not None


def test_build_retrieval_where_all_scope() -> None:
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    expr, summary = build_retrieval_where(
        since,
        source_scope="all",
        min_level=None,
        source_contains=None,
    )
    assert summary["source_scope"] == "all"
    assert summary["min_level"] is None
    assert summary["source_contains"] is None
    _ = expr


def test_build_retrieval_where_compiled_includes_scope_source_prefix() -> None:
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for scope, needle in (
        ("journal", "journal:"),
        ("docker", "docker:"),
        ("file", "file:"),
    ):
        expr, summary = build_retrieval_where(
            since,
            source_scope=scope,
            min_level=None,
            source_contains=None,
        )
        assert summary["source_scope"] == scope
        assert needle in _compile_where(expr)
    expr_all, _ = build_retrieval_where(
        since,
        source_scope="all",
        min_level=None,
        source_contains=None,
    )
    compiled_all = _compile_where(expr_all).lower()
    assert "journal:" not in compiled_all
    assert "docker:" not in compiled_all


def test_build_retrieval_where_without_embedding_omits_embedding_predicate() -> None:
    since = datetime(2025, 1, 1, tzinfo=timezone.utc)
    expr, _ = build_retrieval_where(
        since,
        source_scope="all",
        min_level=None,
        source_contains=None,
        require_embedding=False,
    )
    assert "embedding" not in _compile_where(expr).lower()
