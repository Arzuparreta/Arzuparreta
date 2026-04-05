/**
 * Entry for bundled client script (must live in a top-level layout file so Astro/Vite bundles it).
 */
import { initLocaleClient } from './locale-client';
import { initProjectCaseSiteNav } from './project-case-site';
import { initTheme } from './theme';

export function initHomePageLocale(): void {
	const el = document.getElementById('locale-bundle');
	if (el?.textContent) {
		const bundle = JSON.parse(el.textContent);
		initLocaleClient(bundle);
		initTheme(bundle);
	}
	initProjectCaseSiteNav();
}
