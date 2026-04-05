/**
 * Opens the primary case card’s main external URL when clicking “empty” areas
 * (not links or buttons). URL is projectSiteUrl when set, otherwise repoUrl.
 */
export function initProjectCaseNav(): void {
	for (const article of document.querySelectorAll<HTMLElement>('.case[data-case-nav-url]')) {
		article.addEventListener('click', (e) => {
			if (window.getSelection()?.toString()) return;
			const target = e.target;
			if (!(target instanceof Element)) return;
			if (target.closest('a, button')) return;
			const url = article.dataset.caseNavUrl;
			if (!url) return;
			window.open(url, '_blank', 'noopener,noreferrer');
		});
	}
}
