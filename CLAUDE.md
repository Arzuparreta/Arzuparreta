# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

This is a monorepo for a personal portfolio website with the following structure:

- `portfolio.json` - **Single source of truth**: English + Spanish site copy (`locales.en` / `locales.es`), URLs, GitHub profile README hero (`readme`), and project catalog (`projects.en` / `projects.es` + `projects.slugGroups` for README section ordering)
- `web/` - Astro static site generator (main application)
- `cv/` - CV content in Markdown format
- `projects/` - Pointer docs only; metadata is in `portfolio.json`
- `.github/workflows/` - CI/CD configuration
- `README.md` - GitHub profile README (auto-generated between HTML comment markers—edit `portfolio.json` instead)

**Important**: This repository (`Arzuparreta`) contains the source code and GitHub profile README. The built website is deployed to a separate repository called `Arzuparreta.github.io` via GitHub Actions.

## Development Commands

All commands should be run from the `web/` directory:

```bash
cd web
npm run dev          # Start development server (includes CV copy)
npm run build        # Build for production (includes CV copy)
npm run preview      # Preview production build
npm run ensure-cv    # Copy CV from monorepo root to web public folder
```

## Architecture Overview

### Static Site Generation
- **Framework**: Astro 6.x with static output
- **Deployment**: Cross-repo deployment via GitHub Actions
  - Source repo: `Arzuparreta` (this repository)
  - Target repo: `Arzuparreta.github.io` (separate GitHub Pages repository)
  - Deployment pushes `web/dist/` to `gh-pages` branch of target repo
- **Live site**: https://arzuparreta.github.io
- **Node version**: >=22.12.0

### Internationalization (i18n)
- **Languages**: English (default) and Spanish
- **Implementation**: Client-side locale switching without page reload
- **URL structure**: `/` for English, `/es/` for Spanish
- **Messages**: Loaded from `portfolio.json` → `locales.en` and `locales.es`, re-exported by `src/i18n/en.ts` and `src/i18n/es.ts`
- **Types**: `src/i18n/types.ts` defines the `Messages` interface

### Content Management
- **Portfolio copy + projects**: `portfolio.json` only
- **CV**: Markdown source in `cv/CV.md`, copied to `web/public/resume/CV.md` during build
- **Site URLs + display name**: `portfolio.json` (`urls`, `siteIdentity`), imported in `src/data/site.ts`

### Key Components
- `BaseLayout.astro` - Main layout with HTML structure, meta tags, and client scripts
- `HomePage.astro` - Landing page with intro, skills, and projects
- `ProjectCase.astro` - Primary project cards with media support
- `SmallTool.astro` - Secondary project listings

### Client-Side Scripts
- `locale-client.ts` - Handles locale switching, DOM updates, and History API
- `theme.ts` - Theme switching (light/dark) with localStorage persistence
- `project-case-nav.ts` - Click navigation for project cards
- `page-init.ts` - Entry point for home page client scripts

### Data Loading Patterns
- Projects loaded from `portfolio.json` via `src/data/projects.ts`
- Uses `process.cwd()` for path resolution (not `import.meta.url`)
- Validates project structure with TypeScript types
- Supports primary (detailed cards) and secondary (compact listings) project tiers

### Styling
- **CSS approach**: Scoped CSS in Astro components
- **Global styles**: `src/styles/global.css` with CSS custom properties
- **Theme**: Light/dark mode with CSS variables and data attributes
- **Font**: Outfit Variable font via `@fontsource-variable/outfit`

## Build Process

1. **CV Copy**: `ensure-cv` script copies `cv/CV.md` to `web/public/resume/CV.md`
2. **Astro Build**: Generates static HTML in `web/dist/`
3. **Cross-Repo Deployment**: GitHub Actions deploys `web/dist/` to `gh-pages` branch of `Arzuparreta.github.io` repository
   - Requires `GH_PAGES_DEPLOY_TOKEN` secret in source repo
   - Triggered on push to `main` branch affecting `web/`, `cv/`, `portfolio.json`, or workflow files

## Important Conventions

### Portfolio metadata (`portfolio.json`)
- **`locales.en` / `locales.es`**: Full UI message trees for each language (see `Messages` in `types.ts`)
- **`projects.en` / `projects.es`**: Localized project entries (`slug`, `title`, `tech`, `why`/`how` or `summary`, `tier`, optional media URLs)
- **`projects.slugGroups`**: Maps README sections (`actively`, `maintaining`, `minor`) to ordered slug lists (English `projects.en` is used for GitHub README blurbs)
- **`readme`**: HTML-oriented strings for the GitHub profile README hero (English only)
- Optional **`readmeEmoji`** on English project entries for profile README formatting

### Content Updates
- **Almost everything public-facing**: Edit `portfolio.json`, then run `node scripts/sync-readme.mjs` locally if you want README refreshed before CI
- **CV only**: Edit `cv/CV.md`

### Client Script Bundling
- Client scripts must be imported in layout files to be bundled
- Use `is:inline` sparingly; prefer module scripts for tree-shaking

### Path Resolution
- Example: portfolio path from `web/` uses `join(process.cwd(), '..', 'portfolio.json')`
