/** Default locale for the single-page build. Swap to `'es'` or wire Astro i18n routes when adding `/es/`. */
export const defaultLocale = 'en' as const;

export const supportedLocales = ['en', 'es'] as const;

export type Locale = (typeof supportedLocales)[number];
