import portfolio from '../../../portfolio.json';

/** URLs and display name from `portfolio.json` at repo root. */
export const site = {
	name: portfolio.siteIdentity.displayName,
	handle: 'Arzuparreta',
	url: portfolio.urls.site.replace(/\/$/, ''),
	github: portfolio.urls.github,
	cvRepo: portfolio.urls.cvRepo,
	linkedin: portfolio.urls.linkedin,
	email: portfolio.urls.email,
	openToRelocation: portfolio.siteIdentity.openToRelocation,
} as const;
