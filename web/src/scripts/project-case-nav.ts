/**
 * Opens project URLs when clicking card backgrounds (not links or buttons).
 * Primary cases: projectSiteUrl when set, otherwise repoUrl (`data-case-nav-url`).
 * Smaller tools: repository (`data-tool-repo-url`).
 * Uses delegation on `#projects` so locale updates to `dataset.*` apply without rebinding.
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
		if (caseUrl) {
			window.open(caseUrl, '_blank', 'noopener,noreferrer');
			return;
		}

		const toolEl = target.closest<HTMLElement>('.small-tool');
		const repoUrl = toolEl?.dataset.toolRepoUrl;
		if (repoUrl) {
			window.open(repoUrl, '_blank', 'noopener,noreferrer');
		}
	});
}
