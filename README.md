I've been hooked on computers and hardware for about as long as I can remember. These days, that mostly means maintaining a homelab I actually use every day, in which I generally deploy containerized small tools that solve my inmediate problems. I was trained as a classical trombonist, so my head lives happily between scores and shell prompts.

For projects, stack, and the tidier story, tap through below.

<p align="center">
  <a href="https://arzuparreta.github.io/">Portfolio</a> ·
  <a href="https://arzuparreta.github.io/resume/CV.md">CV</a> ·
  <a href="https://www.linkedin.com/in/rub%C3%A9n-pe%C3%B1a-432953378/">LinkedIn</a> ·
  <a href="mailto:rubenpenarubio02@gmail.com">Email</a>
</p>

## Lab Monorepo Model

This repository now acts as a catalog-first personal lab monorepo.

- Projects are integrated in `projects/repos/` as subtrees from standalone repositories.
- Classification is metadata-driven in `catalog/projects.yaml` and `catalog/taxonomy.yaml`.
- New project kinds are added by extending taxonomy tags and profiles, not by redesigning folders.
- Cross-project tooling belongs in `platform/`; homelab and ops definitions belong in `systems/`.
