"""Planner system prompt rules (roadmap A6)."""

from query.agent_loop import PLANNER_SYSTEM


def test_planner_system_prefers_all_scope_when_no_rows() -> None:
    assert "rows_fetched_so_far" in PLANNER_SYSTEM
    assert "source_scope" in PLANNER_SYSTEM and '"all"' in PLANNER_SYSTEM
    assert "list_sources" in PLANNER_SYSTEM
