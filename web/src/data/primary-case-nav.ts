import type { PrimaryProject } from './projects';

/** Title link and primary card background: official site when set, otherwise GitHub. */
export function primaryCaseNavUrl(p: PrimaryProject): string | undefined {
	return p.projectSiteUrl ?? p.repoUrl;
}
