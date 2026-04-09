# Local sysadmin copilot vision, tools layer, and grounding

## Status

Accepted

## Context

logpilot started as **self-hosted log intelligence** (ingest → Postgres + pgvector → local LLM Q&A). The desired direction is broader: a **local operations assistant** that can use **many read-only signals** (logs, Docker, disk, thermals, GPU, etc.) for **portfolio** and **homelab** use, while keeping **privacy** and **trust** (no cloud dependency by default).

That expansion risks **unsafe patterns** (unconstrained shell from the model), **hallucinated answers**, and **scope creep** without a clear architecture.

## Decision

1. **Positioning:** Treat **logs + embeddings + RAG** as the **first mature pillar**; additional host capabilities arrive as **explicit connectors** behind a unified **tools / probes layer**, documented in [`../plans/local-sysadmin-copilot-roadmap.md`](../plans/local-sysadmin-copilot-roadmap.md).

2. **Tools vs raw shell:** The model may **select named, allowlisted operations** with **structured inputs and outputs**. It must **not** be given a general **shell escape** to run arbitrary commands. New capabilities are added as **code-reviewed tool implementations**, not dynamic prompt text.

3. **Grounding:** User-facing answers must be **evidence-backed**: **retrieved log rows**, **tool outputs**, or an explicit statement that **data is unavailable**. “Helpful” speculation without sources is **out of policy** for this product direction.

4. **Writes and automation:** **Mutating** the system (services, packages, configs) is **out of scope** until the read-path and tooling contracts are stable; any future write path requires its **own ADR** and **human-in-the-loop or hard gates**.

5. **Orchestration:** Multi-step behavior (including “adjust query flags / call tools”) stays **bounded** (steps, timeouts, row limits)—aligned with existing **query agent** limits in configuration, evolving toward **explicit tool-calling** rather than opaque prompt expansion.

## Consequences

- New probes require **tests**, **README / `.env.example`** when configurable, and **MAINTAIN** matrix updates.
- **Portfolio narrative** emphasizes **safe integration** (allowlisted tools, local LLM, grounding) rather than “AI runs your server.”
- Agents should **not** revert to **one-shot shell from the LLM** for feature velocity; add a **tool** instead.
- Superseding this decision requires a new ADR that explicitly replaces the tools / grounding policy.
