/**
 * Opens the primary case card’s main external URL when clicking “empty” areas
 * (not links or buttons). URL is projectSiteUrl when set, otherwise repoUrl.
 * Uses delegation on `#projects` so `data-case-nav-url` updates from locale switching apply without rebinding.
 * The media column uses a real `<a>` (see ProjectCase.astro) so logos/screenshots open without relying on this.
 */
export function initProjectCaseNav(): void {
	const section = document.getElementById('projects');
	if (!section) return;

	section.addEventListener('click', (e) => {
		if (window.getSelection()?.toString()) return;
		const target = e.target;
		if (!(target instanceof Element)) return;
		if (target.closest('a, button')) return;

		const caseEl = target.closest<HTMLElement>('.case');
		const caseUrl = caseEl?.dataset.caseNavUrl;
		if (!caseUrl) return;
		window.open(caseUrl, '_blank', 'noopener,noreferrer');
	});
}
