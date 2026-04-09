# Decision: Live read-only probes (Docker Engine) for `ask`

## Context

`logpilot ask` was built as **RAG over embedded logs** plus optional **on-demand `journalctl`** for host-level grounding. Many operator questions (e.g. container restart counts) need **live structured facts** from the Docker Engine API, not similarity search over stdout/stderr lines.

## Decision

Add an **allowlisted, read-only** query path that calls Docker Engine **GET** endpoints only (`/containers/json`, `/containers/{id}/json`) when:

1. **`DOCKER_QUERY_ON_DEMAND=true`** (default **true** in settings; Compose sets it explicitly and mounts the socket — set **`false`** to opt out), and  
2. The Unix socket exists at **`DOCKER_SOCKET_PATH`**, and  
3. The **intent model** sets **`docker_engine_on_demand`**.

No `docker run`, exec, or write operations. Output is capped before the answer LLM.

## Non-goals

- Arbitrary shell or “run any command the model asks for.”  
- **`docker events`** in this iteration (optional follow-up for calendar-window restart counts).  
- Replacing log ingestion; engine inspect complements RAG, does not substitute it.

## Consequences

- **Docker Compose** ships with the socket mounted read-only and live inspect enabled; host-only installs need the socket path reachable to use engine queries.  
- Intent prompts must distinguish **host OS reboot** (`journalctl --list-boots`) from **container restarts** (inspect table).
