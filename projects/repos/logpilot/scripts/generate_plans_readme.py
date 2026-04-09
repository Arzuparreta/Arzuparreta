#!/usr/bin/env python3
"""Regenerate the plans table in docs/plans/README.md from YAML frontmatter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PLANS_DIR = REPO_ROOT / "docs" / "plans"
README_PATH = PLANS_DIR / "README.md"
MARKER_START = "<!-- plans-index-start -->"
MARKER_END = "<!-- plans-index-end -->"


def parse_frontmatter(raw: str) -> tuple[dict[str, str | bool], str]:
    """Parse a leading --- ... --- YAML-like block; values are strings or bools only."""
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        return {}, raw
    block = raw[4:end]
    body = raw[end + 5 :]
    data: dict[str, str | bool] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        val = rest.strip()
        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
            data[key] = val[1:-1]
        elif val.lower() == "true":
            data[key] = True
        elif val.lower() == "false":
            data[key] = False
        else:
            data[key] = val
    return data, body


def collect_index_rows() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for path in sorted(PLANS_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        fm, _ = parse_frontmatter(text)
        if not fm:
            print(f"error: missing YAML frontmatter in {path.relative_to(REPO_ROOT)}", file=sys.stderr)
            sys.exit(1)
        if "plan_index" not in fm:
            print(
                f"error: add plan_index: true or false to frontmatter in "
                f"{path.relative_to(REPO_ROOT)}",
                file=sys.stderr,
            )
            sys.exit(1)
        if not fm.get("plan_index", False):
            continue
        focus = fm.get("focus")
        if not focus or not isinstance(focus, str):
            print(
                f"error: plan_index: true requires string 'focus' in {path.relative_to(REPO_ROOT)}",
                file=sys.stderr,
            )
            sys.exit(1)
        rows.append((path.name, focus))
    return rows


def render_table(rows: list[tuple[str, str]]) -> str:
    lines = [
        "| Plan | Focus |",
        "| ---- | ----- |",
    ]
    for name, focus in rows:
        lines.append(f"| [`{name}`]({name}) | {focus} |")
    return "\n".join(lines) + "\n"


def splice_readme(generated: str) -> str:
    text = README_PATH.read_text(encoding="utf-8")
    if MARKER_START not in text or MARKER_END not in text:
        print(
            f"error: {README_PATH.relative_to(REPO_ROOT)} must contain "
            f"{MARKER_START!r} and {MARKER_END!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    before, rest = text.split(MARKER_START, 1)
    _, after = rest.split(MARKER_END, 1)
    inner = f"\n{generated}\n"
    return before + MARKER_START + inner + MARKER_END + after


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if README would change (for CI / make check)",
    )
    args = parser.parse_args()
    rows = collect_index_rows()
    generated = render_table(rows)
    new_readme = splice_readme(generated)
    if args.check:
        current = README_PATH.read_text(encoding="utf-8")
        if current != new_readme:
            print(
                "error: docs/plans/README.md is out of date; run: make plans-index",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        README_PATH.write_text(new_readme, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
