import publicEn from '../../../profile/public.en.json';

/** Identity and URLs from `profile/public.en.json` — UI copy in `src/i18n/`. */
export const site = {
	name: publicEn.siteLocale.name,
	handle: 'Arzuparreta',
	url: publicEn.urls.site.replace(/\/$/, ''),
	github: publicEn.urls.github,
	cvRepo: publicEn.urls.cvRepo,
	linkedin: publicEn.urls.linkedin,
	email: publicEn.urls.email,
	openToRelocation: publicEn.siteLocale.openToRelocation,
} as const;
