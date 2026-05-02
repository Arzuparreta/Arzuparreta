/**
 * Technical projects metadata loaded from `portfolio.json` in the hub repo.
 * Site sections follow `projects.slugGroups` (same order as the GitHub profile README).
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import type { Locale } from '../i18n/config';

function portfolioJsonPath(): string {
	return join(process.cwd(), '..', 'portfolio.json');
}

export type ProjectTier = 'primary' | 'secondary';

/** Keys match README / sync-readme.mjs section buckets. */
export type ProjectSectionKey = 'actively' | 'maintaining' | 'minor';

export const PROJECT_SECTION_KEYS: ProjectSectionKey[] = ['actively', 'maintaining', 'minor'];

export type PrimaryProject = {
	slug: string;
	title: string;
	tech: string;
	why: string;
	how: [string] | [string, string];
	repoUrl?: string;
	projectSiteUrl?: string;
	tier: 'primary';
	imageSrc?: string;
	imagePresentation?: 'logo' | 'screenshot';
	demoUrl?: string;
};

export type SecondaryProject = {
	slug: string;
	title: string;
	tech: string;
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
	const ctx = `portfolio.json → projects.${locale}[${index}]`;
	if (raw === null || typeof raw !== 'object') throw new Error(`${ctx}: entry must be an object`);
	const o = raw as Record<string, unknown>;
	const tier = o.tier;
	if (tier === 'primary') return parsePrimary(o, ctx);
	if (tier === 'secondary') return parseSecondary(o, ctx);
	throw new Error(`${ctx}: "tier" must be "primary" or "secondary"`);
}

function loadLocaleArray(raw: unknown, locale: Locale): Project[] {
	if (!Array.isArray(raw)) throw new Error(`portfolio.json: "projects.${locale}" must be an array`);
	return raw.map((item, i) => parseProject(item, locale, i));
}

function parseSlugGroups(raw: unknown): Record<ProjectSectionKey, string[]> {
	if (raw === null || typeof raw !== 'object') throw new Error('portfolio.json: projects.slugGroups must be an object');
	const o = raw as Record<string, unknown>;
	const out = {} as Record<ProjectSectionKey, string[]>;
	for (const key of PROJECT_SECTION_KEYS) {
		const arr = o[key];
		if (!Array.isArray(arr) || !arr.every((s) => typeof s === 'string')) {
			throw new Error(`portfolio.json: projects.slugGroups.${key} must be an array of strings`);
		}
		out[key] = arr as string[];
	}
	return out;
}

function orderBySlugs(projects: Project[], slugs: string[], bucket: string): Project[] {
	const map = new Map(projects.map((p) => [p.slug, p]));
	return slugs.map((slug) => {
		const p = map.get(slug);
		if (!p) throw new Error(`portfolio.json: slugGroups.${bucket} references unknown slug "${slug}" for this locale`);
		return p;
	});
}

type LoadedPortfolio = {
	byLocale: Record<Locale, Project[]>;
	slugGroups: Record<ProjectSectionKey, string[]>;
};

function loadPortfolio(): LoadedPortfolio {
	const path = portfolioJsonPath();
	let parsed: unknown;
	try {
		parsed = JSON.parse(readFileSync(path, 'utf8'));
	} catch (e) {
		const msg = e instanceof Error ? e.message : String(e);
		throw new Error(`portfolio.json: failed to read or parse ${path}: ${msg}`);
	}
	if (parsed === null || typeof parsed !== 'object') throw new Error('portfolio.json: root must be an object');
	const root = parsed as Record<string, unknown>;
	const projects = root.projects;
	if (projects === null || typeof projects !== 'object') throw new Error('portfolio.json: missing "projects" object');
	const p = projects as Record<string, unknown>;
	const slugGroups = parseSlugGroups(p.slugGroups);
	return {
		byLocale: {
			en: loadLocaleArray(p.en, 'en'),
			es: loadLocaleArray(p.es, 'es'),
		},
		slugGroups,
	};
}

const { byLocale, slugGroups } = loadPortfolio();

export function getProjects(locale: Locale): Project[] {
	return byLocale[locale];
}

/** Projects grouped like the GitHub README: actively → maintaining → minor. */
export function getProjectSections(locale: Locale): Record<ProjectSectionKey, Project[]> {
	const list = byLocale[locale];
	return {
		actively: orderBySlugs(list, slugGroups.actively, 'actively'),
		maintaining: orderBySlugs(list, slugGroups.maintaining, 'maintaining'),
		minor: orderBySlugs(list, slugGroups.minor, 'minor'),
	};
}

/** Compact line for the “minor” README bucket (`why` for primary, `summary` for secondary). */
export function projectAsSmallTool(p: Project): SecondaryProject {
	if (p.tier === 'secondary') return p;
	const repoUrl = p.repoUrl;
	if (!repoUrl) {
		throw new Error(`portfolio.json: primary project "${p.slug}" needs repoUrl when listed under slugGroups.minor`);
	}
	return {
		slug: p.slug,
		title: p.title,
		tech: p.tech,
		summary: p.why,
		repoUrl,
		tier: 'secondary',
	};
}
