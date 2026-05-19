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
		contactCta: string;
		contactCtaSubject: string;
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
			/** Same buckets as GitHub profile README (`slugGroups`). */
			activelyDeveloping: string;
			maintaining: string;
			outOfFocus: string;
			githubCta: string;
			/** CTA for compact lines in the “out of focus” bucket. */
			githubCtaSmall: string;
			demoYoutubeCta: string;
			/** Appended to project title in screenshot `alt` (localized). */
			projectImageAltSuffix: string;
		};
		cv: { cvRepo: string };
	};
	profileLead: string;
	availability: {
		status: string;
		note: string;
	};
	about: {
		heading: string;
		p1: string;
		p2: string;
		p3: string;
	};
	services: {
		heading: string;
		intro: string;
		infra: { title: string; desc: string; bullet1: string; bullet2: string; bullet3: string; cta: string; ctaSubject: string };
		audit: { title: string; desc: string; bullet1: string; bullet2: string; bullet3: string; cta: string; ctaSubject: string };
		oss: { title: string; desc: string; bullet1: string; bullet2: string; bullet3: string; cta: string; ctaSubject: string };
	};
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
