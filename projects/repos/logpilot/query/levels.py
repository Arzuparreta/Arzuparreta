"""Log level names aligned with `ingestor.journal` (`PRIORITY` → short string)."""

from __future__ import annotations

# Same order as journal `_PRIO_TO_LEVEL`: lower index = more severe.
_LEVEL_NAMES: tuple[str, ...] = ("emerg", "alert", "crit", "err", "warning", "notice", "info", "debug")

LEVEL_PRIORITY: dict[str, int] = {name: i for i, name in enumerate(_LEVEL_NAMES)}

# Common synonyms → canonical stored form
_LEVEL_ALIASES: dict[str, str] = {
    "error": "err",
    "critical": "crit",
    "warn": "warning",
    "trace": "debug",
}


def normalize_log_level(raw: object) -> str | None:
    """Return canonical level name or None if unknown / empty."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        return None
    t = raw.strip().lower()
    if not t:
        return None
    t = _LEVEL_ALIASES.get(t, t)
    if t in LEVEL_PRIORITY:
        return t
    return None


def allowed_levels_at_or_above_severity(min_level: str) -> frozenset[str]:
    """Include `min_level` and all more-severe levels (e.g. err → emerg…err)."""
    p = LEVEL_PRIORITY[min_level]
    return frozenset(n for n, i in LEVEL_PRIORITY.items() if i <= p)
