# Eval suites (JSON)

## Human review

The canonical question list for batch eval is **`default_questions.json`** in this directory (100+ prompts across hardware probes, systemd services, Docker, journal/file scopes, reboots, and edge cases). **Edit that file** when you want to change what gets asked; keep IDs stable if you compare runs over time.

Optional: maintain a prose outline elsewhere—**the JSON file is what the runner loads.**

## Schema

Root object:

| Field | Type | Required |
|-------|------|----------|
| `version` | int | recommended (currently `1`) |
| `description` | string | optional |
| `items` | array | **required** |

Each **item**:

| Field | Type | Default | Notes |
|-------|------|---------|-------|
| `id` | string | — | Stable identifier for `summary.json` |
| `question` | string | — | Natural-language prompt |
| `tags` | string[] | `[]` | For your own grouping / reports |
| `since` | string | (intent) | e.g. `1h`, `7d` — overrides inferred window |
| `top_k` | int | (intent) | 1–200 |
| `source_scope` | string | (intent) | `all` \| `journal` \| `docker` \| `file` |
| `min_level` | string | (intent) | Syslog severity floor |
| `source_contains` | string | (intent) | Substring filter on source |
| `use_intent` | bool | `true` | Set `false` for raw question only |
| `agent` | bool | `false` | Bounded multi-step retrieval planner |

## Example item

```json
{
  "id": "example_nginx",
  "question": "Any nginx errors in the last day?",
  "tags": ["web", "nginx"],
  "since": "24h",
  "agent": false
}
```
