/**
 * CV page only: theme toggle without home locale switching / popstate handling.
 */
import { initTheme } from './theme';
import type { LocaleBundle } from './locale-client';

export function initCvPageTheme(bundle: LocaleBundle): void {
	initTheme(bundle);
}
