# Journal ingestion: journalctl subprocess and `journal_cursors`

## Status

Accepted

## Context

Host logs on modern Linux are split between the **systemd journal** and plain-text files. File-only ingestion misses journal-only services. Alternatives included Python **libsystemd** bindings, which add native build and packaging complexity.

## Decision

- Ingest the journal with a **`journalctl` subprocess**: `--follow --output=json` and **`--cursor=…`** for idempotent resume after restart.
- Store the resume token in a dedicated **`journal_cursors`** table keyed by **`machine_id`** (not in `ingest_offsets`, which is file-path keyed).
- When journal ingestion is enabled, **omit** default plain-text paths **`/var/log/syslog`** and **`/var/log/messages`** unless `TEXT_LOG_INCLUDE_JOURNAL_DUPLICATE_PATHS` is set, to avoid rsyslog duplicates.

## Consequences

- The runtime image includes a **`journalctl`** binary (`systemd` package in Docker).
- Operators mounting the host journal should set **`JOURNAL_DIRECTORY`** (e.g. `/var/log/journal`) when running in Docker.
- **`JOURNAL_MACHINE_ID`** can be set to the host’s `/etc/machine-id` so cursor rows stay stable across container recreates.
