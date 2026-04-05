/**
 * Persists light/dark preference in localStorage; when unset, follows `prefers-color-scheme`.
 */
import type { Locale } from '../i18n/config';
import type { LocaleBundle } from './locale-client';

const STORAGE_KEY = 'theme';

function getLocaleFromPath(pathname: string, baseUrl: string): Locale {
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

function getStoredTheme(): 'light' | 'dark' | null {
	try {
		const v = localStorage.getItem(STORAGE_KEY);
		if (v === 'light' || v === 'dark') return v;
	} catch {
		/* ignore */
	}
	return null;
}

export function getEffectiveTheme(): 'light' | 'dark' {
	const d = document.documentElement.getAttribute('data-theme');
	if (d === 'light' || d === 'dark') return d;
	return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function setThemeColorMeta(effective: 'light' | 'dark'): void {
	const el = document.getElementById('theme-color-meta');
	if (!el) return;
	el.setAttribute('content', effective === 'dark' ? '#0a0a0f' : '#eceef4');
}

export function refreshThemeButton(bundle: LocaleBundle): void {
	const btn = document.getElementById('theme-toggle');
	if (!btn) return;

	const locale = getLocaleFromPath(window.location.pathname, bundle.baseUrl);
	const m = bundle.messages[locale];
	const effective = getEffectiveTheme();

	btn.classList.toggle('theme-toggle--effective-dark', effective === 'dark');
	btn.setAttribute('aria-pressed', effective === 'dark' ? 'true' : 'false');
	btn.setAttribute(
		'aria-label',
		effective === 'dark' ? m.theme.switchToLight : m.theme.switchToDark,
	);

	setThemeColorMeta(effective);
}

export function initTheme(bundle: LocaleBundle): void {
	const btn = document.getElementById('theme-toggle');
	if (!btn) return;

	const applyFlip = (): void => {
		const next = getEffectiveTheme() === 'dark' ? 'light' : 'dark';
		document.documentElement.setAttribute('data-theme', next);
		try {
			localStorage.setItem(STORAGE_KEY, next);
		} catch {
			/* ignore */
		}
		refreshThemeButton(bundle);
	};

	btn.addEventListener('click', applyFlip);

	const mq = window.matchMedia('(prefers-color-scheme: dark)');
	mq.addEventListener('change', () => {
		if (!getStoredTheme()) {
			document.documentElement.removeAttribute('data-theme');
			refreshThemeButton(bundle);
		}
	});

	refreshThemeButton(bundle);
}
