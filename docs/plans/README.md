# Plans

Longer-lived **execution plans** (scoped work, sequencing, exit criteria). For **why** a design choice was made, use [`../decisions/`](../decisions/) (ADR-lite). For **what to update when you change code**, use [`../agents/MAINTAIN.md`](../agents/MAINTAIN.md).

**Retiring plans:** Move finished markdown into [`archive/`](archive/) (see [archive/README.md](archive/README.md)) when you want to keep links stable, or delete when nothing references the file. Capture durable rationale in [`../decisions/`](../decisions/); git history keeps removed files.

The table below is **generated** from YAML frontmatter in each plan file. After adding, renaming, or changing `plan_index` / `focus`, run **`make plans-index`** (or `make check`, which verifies it).

<!-- plans-index-start -->
| Plan | Focus |
| ---- | ----- |
| [`journal-host-visibility-doctor-and-parsed-service-fields.md`](journal-host-visibility-doctor-and-parsed-service-fields.md) | Journal ingest UX, `logpilot doctor`, optional `parsed` service identity |
| [`local-sysadmin-copilot-roadmap.md`](local-sysadmin-copilot-roadmap.md) | **Direction:** grounded local ops copilot, tools layer, phased roadmap (logs → probes → orchestration → UI) |

<!-- plans-index-end -->
