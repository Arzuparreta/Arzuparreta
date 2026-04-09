/**
 * Client-side locale switching without full page reload: updates DOM + History API.
 * Scroll position is preserved because navigation is not a document load.
 */
import type { Locale } from '../i18n/config';
import type { Messages } from '../i18n/types';
import { primaryCaseNavUrl } from '../data/primary-case-nav';
import type { PrimaryProject, SecondaryProject } from '../data/projects';
import { refreshThemeButton } from './theme';

export type LocaleBundle = {
	baseUrl: string;
	siteUrl: string;
	messages: Record<Locale, Messages>;
	projects: Record<Locale, { primary: PrimaryProject[]; secondary: SecondaryProject[] }>;
};

function getNested(obj: unknown, path: string): string | undefined {
	const parts = path.split('.');
	let cur: unknown = obj;
	for (const p of parts) {
		if (cur == null || typeof cur !== 'object') return undefined;
		cur = (cur as Record<string, unknown>)[p];
	}
	return typeof cur === 'string' ? cur : undefined;
}

function localePathFromBase(baseUrl: string, locale: Locale): string {
	if (locale === 'es') {
		if (baseUrl === '/' || baseUrl === '') return '/es/';
		const base = baseUrl.replace(/\/$/, '');
		return `${base}/es/`;
	}
	if (baseUrl === '/' || baseUrl === '') return '/';
	return baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`;
}

/** Compare pathnames ignoring a trailing slash (except root). */
function pathnameMatches(a: string, b: string): boolean {
	const strip = (p: string) => {
		if (p === '/' || p === '') return '/';
		return p.replace(/\/$/, '');
	};
	return strip(a) === strip(b);
}

export function getLocaleFromPath(pathname: string, baseUrl: string): Locale {
	if (baseUrl === '/' || baseUrl === '') {
		const trimmed = pathname.replace(/^\/+|\/+$/g, '');
		if (trimmed === 'es' || trimmed.startsWith('es/')) return 'es';
		return 'en';
	}
	const base = baseUrl.replace(/\/$/, '');
	if (!pathname.startsWith(base)) return 'en';
	let rest = pathname.slice(base.length);
	rest = rest.replace(/^\/+|\/+$/g, '');
	if (rest === 'es' || rest.startsWith('es/')) return 'es';
	return 'en';
}

function updateHead(m: Messages, siteUrl: string, locale: Locale): void {
	const canonicalPath = locale === 'es' ? '/es/' : '/';
	const canonical = new URL(canonicalPath, siteUrl).href;
	const ogLocale = locale === 'es' ? 'es_ES' : 'en_GB';

	document.title = m.meta.title;

	document.querySelector('meta[name="description"]')?.setAttribute('content', m.meta.description);
	document.querySelector('meta[property="og:title"]')?.setAttribute('content', m.meta.title);
	document.querySelector('meta[property="og:description"]')?.setAttribute('content', m.meta.description);
	document.querySelector('meta[property="og:url"]')?.setAttribute('content', canonical);
	document.querySelector('meta[property="og:locale"]')?.setAttribute('content', ogLocale);
	document.querySelector('meta[name="twitter:title"]')?.setAttribute('content', m.meta.title);
	document.querySelector('meta[name="twitter:description"]')?.setAttribute('content', m.meta.description);
	document.querySelector('link[rel="canonical"]')?.setAttribute('href', canonical);
}

function applyTechnicalSkills(ul: Element, lines: string[]): void {
	ul.replaceChildren(
		...lines.map((line) => {
			const li = document.createElement('li');
			li.className = 'skill-chip';
			li.textContent = line;
			return li;
		}),
	);
}

function applyPrimaryCase(
	article: HTMLElement,
	project: PrimaryProject,
	githubCta: string,
	demoYoutubeCta: string,
	projectImageAltSuffix: string,
): void {
	const titleLink = article.querySelector<HTMLAnchorElement>('.case__title-link');
	const titleText = article.querySelector('.case__title-text');
	const tech = article.querySelector('.case__tech');
	const why = article.querySelector('.case__why');
	const how = article.querySelector('.case__how');
	const githubLink = article.querySelector<HTMLAnchorElement>('.case__github-btn');
	const demoLink = article.querySelector<HTMLAnchorElement>('.case__cta-demo');
	const img = article.querySelector<HTMLImageElement>('.case__img');

	if (titleLink && project.repoUrl) {
		titleLink.textContent = project.title;
		titleLink.href = primaryCaseNavUrl(project) ?? project.repoUrl;
	}
	if (titleText) titleText.textContent = project.title;
	if (tech) tech.textContent = project.tech;
	if (why) why.textContent = project.why;
	if (how) {
		how.replaceChildren(
			...project.how.map((line) => {
				const li = document.createElement('li');
				li.textContent = line;
				return li;
			}),
		);
	}
	if (githubLink && project.repoUrl) {
		githubLink.setAttribute('aria-label', githubCta);
		githubLink.href = project.repoUrl;
	}

	if (demoLink) {
		if (project.demoUrl) {
			demoLink.hidden = false;
			demoLink.href = project.demoUrl;
			demoLink.textContent = demoYoutubeCta;
		} else {
			demoLink.hidden = true;
		}
	}

	if (img && project.imageSrc) {
		img.src = project.imageSrc;
		img.alt = `${project.title}${projectImageAltSuffix}`;
	}

	const navUrl = primaryCaseNavUrl(project);
	if (navUrl) {
		article.dataset.caseNavUrl = navUrl;
	} else {
		delete article.dataset.caseNavUrl;
	}
}

function applySmallTool(article: HTMLElement, tool: SecondaryProject, githubCta: string): void {
	const name = article.querySelector('.small-tool__name');
	const tech = article.querySelector('.small-tool__tech');
	const summary = article.querySelector('.small-tool__summary');
	if (name) name.textContent = tool.title;
	if (tech) tech.textContent = `${tool.tech}.`;
	if (summary) summary.textContent = `${tool.summary} `;
	if (article instanceof HTMLAnchorElement && article.classList.contains('small-tool')) {
		article.href = tool.repoUrl;
		article.setAttribute('aria-label', `${tool.title} — ${githubCta}`);
	}
}

function applyLocale(bundle: LocaleBundle, locale: Locale): void {
	const m = bundle.messages[locale];
	const { primary, secondary } = bundle.projects[locale];

	updateHead(m, bundle.siteUrl, locale);

	document.querySelectorAll<HTMLElement>('[data-i18n]').forEach((el) => {
		const path = el.getAttribute('data-i18n');
		if (!path) return;
		const val = getNested(m as unknown as Record<string, unknown>, path);
		if (val !== undefined) el.textContent = val;
	});

	document.querySelectorAll<HTMLElement>('[data-i18n-aria]').forEach((el) => {
		const path = el.getAttribute('data-i18n-aria');
		if (!path) return;
		const val = getNested(m as unknown as Record<string, unknown>, path);
		if (val !== undefined) el.setAttribute('aria-label', val);
	});

	document.querySelector('.site-bottom-bar')?.setAttribute('aria-label', m.a11y.siteAside);
	document.querySelector('.lang-switcher')?.setAttribute('aria-label', m.language.ariaLabel);

	const skillsUl = document.querySelector('ul.skills');
	if (skillsUl) applyTechnicalSkills(skillsUl, m.technicalSkills);

	for (const p of primary) {
		const article = document.getElementById(p.slug);
		if (article?.classList.contains('case')) {
			applyPrimaryCase(
				article,
				p,
				m.sections.projects.githubCta,
				m.sections.projects.demoYoutubeCta,
				m.sections.projects.projectImageAltSuffix,
			);
		}
	}

	for (const t of secondary) {
		const article = document.getElementById(t.slug);
		if (article?.classList.contains('small-tool')) applySmallTool(article, t, m.sections.projects.githubCtaSmall);
	}

	document.querySelectorAll<HTMLAnchorElement>('.lang-switcher__link').forEach((a) => {
		const target = a.getAttribute('data-locale-target') as Locale | null;
		if (!target) return;
		if (target === locale) {
			a.setAttribute('aria-current', 'page');
		} else {
			a.removeAttribute('aria-current');
		}
	});
	refreshLangToggle(bundle, locale);
	refreshThemeButton(bundle);
}

function refreshLangToggle(bundle: LocaleBundle, locale: Locale): void {
	const btn = document.getElementById('lang-toggle');
	if (!btn) return;
	const m = bundle.messages[locale];
	btn.setAttribute(
		'aria-label',
		locale === 'en' ? m.language.toggleToSpanish : m.language.toggleToEnglish,
	);
}

export function initLocaleClient(bundle: LocaleBundle): void {
	const { baseUrl } = bundle;

	const applyAndSyncHistory = (locale: Locale): void => {
		applyLocale(bundle, locale);
		const path = localePathFromBase(baseUrl, locale);
		if (!pathnameMatches(window.location.pathname, path)) {
			history.pushState({ locale }, '', path);
		}
	};

	document.querySelectorAll<HTMLAnchorElement>('.lang-switcher__link').forEach((a) => {
		a.addEventListener('click', (e) => {
			const target = a.getAttribute('data-locale-target') as Locale | null;
			if (!target) return;
			const current = getLocaleFromPath(window.location.pathname, baseUrl);
			if (target === current) {
				e.preventDefault();
				return;
			}
			e.preventDefault();
			applyAndSyncHistory(target);
		});
	});

	document.getElementById('lang-toggle')?.addEventListener('click', () => {
		const current = getLocaleFromPath(window.location.pathname, baseUrl);
		const next: Locale = current === 'en' ? 'es' : 'en';
		applyAndSyncHistory(next);
	});

	window.addEventListener('popstate', () => {
		const locale = getLocaleFromPath(window.location.pathname, baseUrl);
		applyLocale(bundle, locale);
	});
}
