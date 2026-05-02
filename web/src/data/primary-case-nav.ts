import type { Project } from './projects';


/** Title link and case card background: product URL when set (primary only), otherwise GitHub. */
export function caseNavUrl(p: Project): string | undefined {
	if (p.tier === 'primary') return p.projectSiteUrl ?? p.repoUrl;
	return p.repoUrl;
}

