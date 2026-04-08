/**
 * Technical projects — narratives loaded from monorepo `projects/projects.json` (also copied to `public/data/` by `ensure-projects` for deploy).
 * https://github.com/Arzuparreta
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Locale } from '../i18n/config';

/**
 * Canonical file lives next to `web/` at `projects/projects.json`.
 * Use cwd (always `web/` for `npm run dev` / `build` here), not `import.meta.url` — bundled prerender chunks would resolve the wrong directory.
 */
function projectsJsonPath(): string {
	return join(process.cwd(), '..', 'projects', 'projects.json');
}

export type ProjectTier = 'primary' | 'secondary';

export type PrimaryProject = {
	slug: string;
	title: string;
	/** Comma-separated core technologies (shown after title). */
	tech: string;
	/** What it is and what problem it solves. */
	why: string;
	/** One or two concrete technical or operational details. */
	how: [string] | [string, string];
	/** Public GitHub URL (repo icon; default title/card background target when projectSiteUrl is omitted). Omit when there is no public repo. */
	repoUrl?: string;
	/** Optional product/docs site (e.g. GitHub Pages). When set, title link and card background use this instead of repoUrl; the repo icon still uses repoUrl. */
	projectSiteUrl?: string;
	tier: 'primary';
	/** Optional screenshot path under site root. */
	imageSrc?: string;
	/**
	 * When `imageSrc` is set: how the image is framed in the case card.
	 * `logo` — square app icon (narrow column, capped size). `screenshot` — wide UI capture (default).
	 */
	imagePresentation?: 'logo' | 'screenshot';
	/** Optional external demo (e.g. video). */
	demoUrl?: string;
};

export type SecondaryProject = {
	slug: string;
	title: string;
	tech: string;
	/** Single sentence for compact listing. */
	summary: string;
	repoUrl: string;
	tier: 'secondary';
};

export type Project = PrimaryProject | SecondaryProject;

function isNonEmptyString(v: unknown): v is string {
	return typeof v === 'string' && v.length > 0;
}

function parseHow(raw: unknown, ctx: string): [string] | [string, string] {
	if (!Array.isArray(raw) || raw.length < 1 || raw.length > 2) {
		throw new Error(`${ctx}: "how" must be an array of 1 or 2 strings`);
	}
	const lines = raw.map((line, i) => {
		if (!isNonEmptyString(line)) throw new Error(`${ctx}: how[${i}] must be a non-empty string`);
		return line;
	});
	return lines.length === 1 ? [lines[0]!] : [lines[0]!, lines[1]!];
}

function parsePrimary(o: Record<string, unknown>, ctx: string): PrimaryProject {
	const slug = o.slug;
	const title = o.title;
	const tech = o.tech;
	const why = o.why;
	if (!isNonEmptyString(slug)) throw new Error(`${ctx}: missing or invalid "slug"`);
	if (!isNonEmptyString(title)) throw new Error(`${ctx}: missing or invalid "title"`);
	if (!isNonEmptyString(tech)) throw new Error(`${ctx}: missing or invalid "tech"`);
	if (!isNonEmptyString(why)) throw new Error(`${ctx}: missing or invalid "why"`);
	if (o.tier !== 'primary') throw new Error(`${ctx}: expected tier "primary"`);

	const out: PrimaryProject = {
		slug,
		title,
		tech,
		why,
		how: parseHow(o.how, ctx),
		tier: 'primary',
	};
	if (o.repoUrl !== undefined) {
		if (!isNonEmptyString(o.repoUrl)) throw new Error(`${ctx}: "repoUrl" must be a non-empty string when set`);
		out.repoUrl = o.repoUrl;
	}
	if (o.projectSiteUrl !== undefined) {
		if (!isNonEmptyString(o.projectSiteUrl)) throw new Error(`${ctx}: "projectSiteUrl" must be a non-empty string when set`);
		out.projectSiteUrl = o.projectSiteUrl;
	}
	if (o.imagePresentation !== undefined && o.imageSrc === undefined) {
		throw new Error(`${ctx}: "imagePresentation" is only valid when "imageSrc" is set`);
	}
	if (o.imageSrc !== undefined) {
		if (!isNonEmptyString(o.imageSrc)) throw new Error(`${ctx}: "imageSrc" must be a non-empty string when set`);
		out.imageSrc = o.imageSrc;
		const pres = o.imagePresentation;
		if (pres !== undefined) {
			if (pres !== 'logo' && pres !== 'screenshot') {
				throw new Error(`${ctx}: "imagePresentation" must be "logo" or "screenshot"`);
			}
			out.imagePresentation = pres;
		} else {
			out.imagePresentation = 'screenshot';
		}
	}
	if (o.demoUrl !== undefined) {
		if (!isNonEmptyString(o.demoUrl)) throw new Error(`${ctx}: "demoUrl" must be a non-empty string when set`);
		out.demoUrl = o.demoUrl;
	}
	return out;
}

function parseSecondary(o: Record<string, unknown>, ctx: string): SecondaryProject {
	const slug = o.slug;
	const title = o.title;
	const tech = o.tech;
	const summary = o.summary;
	const repoUrl = o.repoUrl;
	if (!isNonEmptyString(slug)) throw new Error(`${ctx}: missing or invalid "slug"`);
	if (!isNonEmptyString(title)) throw new Error(`${ctx}: missing or invalid "title"`);
	if (!isNonEmptyString(tech)) throw new Error(`${ctx}: missing or invalid "tech"`);
	if (!isNonEmptyString(summary)) throw new Error(`${ctx}: missing or invalid "summary"`);
	if (!isNonEmptyString(repoUrl)) throw new Error(`${ctx}: missing or invalid "repoUrl"`);
	if (o.tier !== 'secondary') throw new Error(`${ctx}: expected tier "secondary"`);
	return { slug, title, tech, summary, repoUrl, tier: 'secondary' };
}

function parseProject(raw: unknown, locale: Locale, index: number): Project {
	const ctx = `projects.json [${locale}][${index}]`;
	if (raw === null || typeof raw !== 'object') throw new Error(`${ctx}: entry must be an object`);
	const o = raw as Record<string, unknown>;
	const tier = o.tier;
	if (tier === 'primary') return parsePrimary(o, ctx);
	if (tier === 'secondary') return parseSecondary(o, ctx);
	throw new Error(`${ctx}: "tier" must be "primary" or "secondary"`);
}

function loadLocaleArray(raw: unknown, locale: Locale): Project[] {
	if (!Array.isArray(raw)) throw new Error(`projects.json: "${locale}" must be an array`);
	return raw.map((item, i) => parseProject(item, locale, i));
}

function loadProjectsFile(): Record<Locale, Project[]> {
	const path = projectsJsonPath();
	let parsed: unknown;
	try {
		parsed = JSON.parse(readFileSync(path, 'utf8'));
	} catch (e) {
		const msg = e instanceof Error ? e.message : String(e);
		throw new Error(`projects.json: failed to read or parse ${path}: ${msg}`);
	}
	if (parsed === null || typeof parsed !== 'object') throw new Error('projects.json: root must be an object');
	const root = parsed as Record<string, unknown>;
	return {
		en: loadLocaleArray(root.en, 'en'),
		es: loadLocaleArray(root.es, 'es'),
	};
}

const byLocale: Record<Locale, Project[]> = loadProjectsFile();

export function getProjects(locale: Locale): Project[] {
	return byLocale[locale];
}

export function getPrimaryProjects(locale: Locale): PrimaryProject[] {
	return getProjects(locale).filter((p): p is PrimaryProject => p.tier === 'primary');
}

export function getSecondaryProjects(locale: Locale): SecondaryProject[] {
	return getProjects(locale).filter((p): p is SecondaryProject => p.tier === 'secondary');
}
