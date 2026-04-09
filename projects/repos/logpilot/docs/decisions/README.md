# Decision log (ADR-lite)

**Purpose:** Preserve *why* a non-obvious choice was made so it is not re-litigated in later work.

**When to add a file:** New pipeline, storage format, branching exception, security boundary, or any change where the reason is not obvious from code alone.

**Naming:** `NNN_short_title.md` (increment `NNN` from the highest existing number).

**Template (copy into a new file):**

```markdown
# Title

## Status

Accepted | Superseded by …

## Context

What problem or constraint triggered this?

## Decision

What we chose.

## Consequences

Trade-offs, follow-ups, things agents must not undo silently.
```

