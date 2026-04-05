/**
 * Entry for bundled client script (must live in a top-level layout file so Astro/Vite bundles it).
 */
import { initLocaleClient } from './locale-client';
import { initProjectCaseNav } from './project-case-nav';
import { initTheme } from './theme';

export function initHomePageLocale(): void {
	const el = document.getElementById('locale-bundle');
	if (el?.textContent) {
		const bundle = JSON.parse(el.textContent);
		initLocaleClient(bundle);
		initTheme(bundle);
	}
	initProjectCaseNav();
}
