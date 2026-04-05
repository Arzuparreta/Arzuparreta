export type Messages = {
	meta: {
		title: string;
		description: string;
	};
	a11y: {
		skipToContent: string;
		siteAside: string;
	};
	nav: {
		ariaLabel: string;
		intro: string;
		skills: string;
		projects: string;
		github: string;
		linkedin: string;
	};
	footer: {
		cvLabel: string;
		mailLabel: string;
		openCvAria: string;
		emailAria: string;
	};
	theme: {
		switchToLight: string;
		switchToDark: string;
	};
	identity: {
		headline: string;
		location: string;
		openToRelocation: string;
	};
	sections: {
		skills: { title: string; intro: string };
		projects: {
			title: string;
			intro: string;
			smallerTools: string;
			githubCta: string;
			/** CTA for compact secondary-project lines (often “repository” vs “config/source”). */
			githubCtaSmall: string;
			demoYoutubeCta: string;
			/** Appended to project title in screenshot `alt` (localized). */
			projectImageAltSuffix: string;
		};
		cv: { cvRepo: string };
	};
	profileLead: string;
	technicalSkills: string[];
	/** Language switcher in the bottom bar. */
	language: {
		ariaLabel: string;
		english: string;
		spanish: string;
		/** Mobile icon button: switch to the other locale. */
		toggleToEnglish: string;
		toggleToSpanish: string;
	};
};
