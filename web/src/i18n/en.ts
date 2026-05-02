import type { Messages } from './types';
import publicEn from '../../../profile/public.en.json';

const { siteLocale } = publicEn;

export const en: Messages = {
	meta: siteLocale.meta,
	a11y: {
		skipToContent: 'Skip to content',
		siteAside: 'Site footer',
	},
	nav: {
		ariaLabel: 'Primary',
		intro: 'Intro',
		skills: 'Skills',
		projects: 'Projects',
		github: 'GitHub',
		linkedin: 'LinkedIn',
	},
	footer: {
		cvLabel: 'CV',
		mailLabel: 'Mail',
		openCvAria: 'Open CV — view online, download, or source on GitHub',
		emailAria: 'Send email',
	},
	theme: {
		switchToLight: 'Switch to light theme',
		switchToDark: 'Switch to dark theme',
	},
	identity: siteLocale.identity,
	sections: {
		skills: siteLocale.sectionsSkills,
		projects: {
			title: 'Projects',
			intro: 'What I built, why it matters, and how it actually runs.',
			smallerTools: 'Smaller Tools & Scripts',
			githubCta: 'View configuration and source code on GitHub',
			githubCtaSmall: 'View repository on GitHub',
			demoYoutubeCta: 'Watch on YouTube',
			projectImageAltSuffix: ' — interface preview',
		},
		cv: {
			cvRepo: 'Source on GitHub',
		},
	},
	profileLead: siteLocale.profileLead,
	technicalSkills: siteLocale.technicalSkills,
	language: {
		ariaLabel: 'Language',
		english: 'English',
		spanish: 'Español',
		toggleToEnglish: 'Switch to English',
		toggleToSpanish: 'Switch to Spanish',
	},
};
