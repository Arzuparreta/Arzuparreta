# Catalog

This catalog is the source of truth for project metadata.

## Purpose

- Keep project classification independent from folder layout.
- Allow arbitrary new project types by extending taxonomy tags.
- Drive automation (CI selection, reporting, search, dashboards) from metadata.

## Files

- `projects.yaml`: project inventory and per-project metadata.
- `taxonomy.yaml`: controlled vocabulary and placement policy.

## How to add a new project

1. Place the project code under `projects/repos/<project-id>` if it is long-lived.
2. Register the project in `catalog/projects.yaml`.
3. Reuse a profile if one fits, or add a new profile in `catalog/taxonomy.yaml`.
4. Keep project-specific bootstrap/test/run commands documented.
