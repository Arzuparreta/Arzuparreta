from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_REL = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)


def parse_since(s: str) -> datetime:
    raw = s.strip()
    now = datetime.now(timezone.utc)
    m = _REL.match(raw.lower())
    if m:
        n = int(m.group(1))
        u = m.group(2).lower()
        delta = {
            "s": timedelta(seconds=n),
            "m": timedelta(minutes=n),
            "h": timedelta(hours=n),
            "d": timedelta(days=n),
        }[u]
        return now - delta
    try:
        iso = raw.replace("Z", "+00:00").replace("z", "+00:00")
        ts = datetime.fromisoformat(iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except ValueError as exc:
        raise ValueError(f"invalid --since {raw!r}; use e.g. 1h, 30m, 7d or ISO-8601") from exc


def is_valid_since(s: str) -> bool:
    try:
        parse_since(s)
        return True
    except ValueError:
        return False
