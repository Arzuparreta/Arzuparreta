# Optional `service_key` / `service_label` in `Log.parsed`

## Status

Accepted

## Context

Journal, Docker, and plain-text ingest share one `parsed` JSONB column. Operators and retrieval need a **stable, documented** service identity for prompts and filters without a new indexed column or migration.

## Decision

- Add optional **`service_key`** and **`service_label`** at ingest time (additive JSONB only).
- **Journal:** `unit:…` from `_SYSTEMD_UNIT` / `UNIT`, else `syslog_id:…`, else `comm:…`; if none, **omit** both keys (no sentinel like `journal:unknown`).
- **Docker:** `docker:<name>` or `docker:<short_id>`.
- **Plain-text `file:`:** **v1 does not set** these keys; syslog tag parsing is deferred.

## Consequences

- Historical rows are unchanged (forward-only).
- README and inventory preamble document the convention for answer models.
- Future indexed columns for service identity would require a migration and MAINTAIN updates.
