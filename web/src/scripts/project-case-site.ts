/**
 * Opens the project landing page when clicking “empty” areas of a case card
 * (not links or buttons). Title link href is set in markup from project data.
 */
export function initProjectCaseSiteNav(): void {
	for (const article of document.querySelectorAll<HTMLElement>('.case[data-project-site-url]')) {
		const url = article.dataset.projectSiteUrl;
		if (!url) continue;

		article.addEventListener('click', (e) => {
			if (window.getSelection()?.toString()) return;
			const target = e.target;
			if (!(target instanceof Element)) return;
			if (target.closest('a, button')) return;
			window.open(url, '_blank', 'noopener,noreferrer');
		});
	}
}
