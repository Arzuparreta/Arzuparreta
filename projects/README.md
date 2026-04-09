# Projects Workspace

This directory mixes two concerns on purpose:

- `projects.json`: public portfolio project catalog consumed by the website.
- `repos/`: imported standalone repositories integrated into this monorepo.

## Monorepo sync model

- Upstream project repos are imported as subtrees into `projects/repos/<name>`.
- Local monorepo improvements can be developed across multiple projects together.
- If needed later, changes can be pushed back to standalone repos with `git subtree push`.

## Adding another repository

Use:

`git subtree add --prefix="projects/repos/<name>" "https://github.com/<owner>/<repo>.git" main --squash`

Then register metadata in `catalog/projects.yaml`.
