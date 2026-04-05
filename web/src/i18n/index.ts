/**
 * UI strings for the site. English is at `/`, Spanish at `/es/` via `HomePage` and `getMessages('es')`.
 * Project narratives are localized in `data/projects.ts` (`getPrimaryProjects` / `getSecondaryProjects`).
 */
export type { Locale } from './config';
export { defaultLocale, supportedLocales } from './config';
export type { Messages } from './types';
export { en } from './en';
export { es } from './es';

import type { Locale } from './config';
import type { Messages } from './types';
import { en } from './en';
import { es } from './es';

const byLocale: Record<Locale, Messages> = {
	en,
	es,
};

export function getMessages(locale: Locale): Messages {
	return byLocale[locale];
}
