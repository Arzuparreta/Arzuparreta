# Soundsible landing

Marketing site for [Soundsible](https://github.com/Arzuparreta/Arzuparreta/tree/main/projects/repos/soundsible).

This app lives in this repository at `projects/repos/soundsible-site`.
The public entry point is the portfolio site at `https://arzuparreta.github.io/`.

## Stack

- [Astro](https://astro.build/) 5 + [Tailwind CSS](https://tailwindcss.com/)
- Typography: [Outfit Variable](https://fonts.google.com/specimen/Outfit) + [DM Sans Variable](https://fonts.google.com/specimen/DM+Sans)
- Motion: [Motion One](https://motion.dev/) (scroll reveals; respects `prefers-reduced-motion`)

Design tokens match the Soundsible Station shell (dark background `#0a0a0c` / `#0d0d0f`, accent `#f97a12`, secondary `#3178c6`).

## Local development

```bash
npm install
npm run dev
```

Use the URL Astro prints.

```bash
npm run build    # output in dist/
npm run preview  # serve dist locally
```

## Assets

Screenshots and the app logo live under `public/`. To refresh them after a product update, copy from the main Soundsible repo, for example:

- `branding/logo-app.png` → `public/logo-app.png`
- `docs/images/desktop-player-dark.png` → `public/screenshots/` and optionally `public/og-image.png`
- Mobile shots from `docs/images/` → `public/screenshots/`

Regenerate `public/favicon.png` from the logo if the icon changes (64×64 PNG is enough).

## Deploy (GitHub Actions)

1. Repository **Settings → Pages**: set **Source** to **GitHub Actions** (not “Deploy from a branch”).
2. Push to `main`. Workflow [.github/workflows/deploy.yml](.github/workflows/deploy.yml) runs `npm ci`, `npm run build`, and publishes `dist/` via the official Pages deploy action.

Ensure **Settings → Actions → General → Workflow permissions** allows read/write for workflows that deploy Pages.

## Updating links

Canonical repository URLs are centralized in [src/constants.ts](src/constants.ts).
