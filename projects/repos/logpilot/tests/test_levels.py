from query.levels import allowed_levels_at_or_above_severity, normalize_log_level


def test_normalize_log_level_aliases() -> None:
    assert normalize_log_level("ERROR") == "err"
    assert normalize_log_level("critical") == "crit"
    assert normalize_log_level("warn") == "warning"


def test_normalize_log_level_invalid() -> None:
    assert normalize_log_level("nope") is None
    assert normalize_log_level("") is None


def test_allowed_levels_err() -> None:
    s = allowed_levels_at_or_above_severity("err")
    assert "err" in s and "info" not in s and "emerg" in s
