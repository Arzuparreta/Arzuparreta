import type { Messages } from './types';

export const en: Messages = {
	meta: {
		title: 'Rubén Peña Rubio — Junior Linux Systems Administrator · DevOps',
		description:
			'Self-taught Linux and infrastructure in Seville: homelab, Docker, Python automation, Debian. Classical musician moving into junior sysadmin / ops work.',
	},
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
	identity: {
		headline: 'Junior Linux Systems Administrator\u00a0|\u00a0DevOps Enthusiast',
		location: 'Seville,\u00a0Spain',
		openToRelocation: 'Open to relocation',
	},
	sections: {
		skills: {
			title: 'Skills',
			intro: 'Operating systems, infrastructure, networking, and tooling I use regularly.',
		},
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
	profileLead:
		'Self-taught systems enthusiast with a decade of hardware tinkering and two years of deep focus on Linux, Docker, and Python automation. I build and maintain reliable homelab infrastructure and containerized services.',
	technicalSkills: [
		'Operating systems: UNIX/Linux (Arch, Debian, Ubuntu)',
		'Infrastructure: Docker, Docker Compose, Portainer',
		'Networking: SSH/Mosh, Tailscale, Samba, VPN',
		'Automation: Python (CLI and API development), Bash, Git',
	],
	language: {
		ariaLabel: 'Language',
		english: 'English',
		spanish: 'Español',
		toggleToEnglish: 'Switch to English',
		toggleToSpanish: 'Switch to Spanish',
	},
};
