/**
 * Regenerates GitHub profile README from `portfolio.json` (urls, readme hero, projects slug groups + en entries).
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const portfolioPath = join(root, 'portfolio.json');
const readmePath = join(root, 'README.md');

const PROFILE_START = '<!-- readme-profile:start -->';
const PROFILE_END = '<!-- readme-profile:end -->';
const PROJECTS_START = '<!-- readme-projects:start -->';
const PROJECTS_END = '<!-- readme-projects:end -->';

const SECTIONS = [
	{ key: 'maintaining', heading: '### MAINTAINING / IMPROVING\n', status: 'MAINTAINING' },
	{ key: 'actively', heading: '### WORK IN PROGRESS\n', status: 'BUILDING' },
	{ key: 'minor', heading: '#### OUT OF FOCUS / UNMAINTAINED\n', status: 'ARCHIVED' },
];

function loadPortfolio() {
	const data = JSON.parse(readFileSync(portfolioPath, 'utf8'));
	if (!data.urls || !data.readme || !data.projects) {
		throw new Error('portfolio.json: expected "urls", "readme", and "projects"');
	}
	return data;
}

function buildReadmeProfile(data) {
	const { urls, readme } = data;
	const mailto = `mailto:${urls.email}`;
	const badges = Array.isArray(readme.toolBadges) ? readme.toolBadges : [];
	const badgeHtml = badges.length > 0 ? `<p align="center">
${badges.map((badge) => `  <img src="${badgeUrl(badge)}" alt="${badge.label} / ${badge.message}">`).join('\n')}
</p>

` : '';
	const statusRows = Array.isArray(readme.statusRows) ? readme.statusRows : [];
	const statusHtml = statusRows.length > 0 ? `<table align="center">
${statusRows.map((row) => `  <tr>
    <td><strong>${row.label}</strong></td>
    <td>${row.value}</td>
  </tr>`).join('\n')}
</table>

` : '';
	const focus = typeof readme.currentlyFocusedMarkdown === 'string' && readme.currentlyFocusedMarkdown.length > 0
		? `${readme.currentlyFocusedMarkdown}\n\n`
		: '';
	return `<h1 align="center">${readme.nameHeading}</h1>

<p align="center">
  <strong>${readme.subtitleHtml}</strong>
</p>

<p align="center">
${readme.taglineWithBreak}
</p>

<p align="center"> 
  ${readme.taglineEmphasisLine1}${readme.taglineEmphasisLine2 ? `<br>\n  ${readme.taglineEmphasisLine2}` : ''}
</p>

${readme.contextLine ? `<p align="center">
  <sub>${readme.contextLine}</sub>
</p>

` : ''}<p align="center">
  <a href="${urls.site}">PORTFOLIO</a>
  &nbsp;/&nbsp;
  <a href="${urls.linkedin}">LINKEDIN</a>
  &nbsp;/&nbsp;
  <a href="${mailto}">EMAIL</a>
</p>

${badgeHtml}${statusHtml}${focus}`;
}

function badgeUrl(badge) {
	const label = encodeURIComponent(String(badge.label ?? ''));
	const message = encodeURIComponent(String(badge.message ?? ''));
	const color = encodeURIComponent(String(badge.color ?? '111111').replace(/^#/, ''));
	return `https://img.shields.io/badge/${label}-${message}-${color}?style=flat-square`;
}

function loadProjectsPayload(portfolio) {
	const { projects } = portfolio;
	const readme = projects.slugGroups;
	if (readme === null || typeof readme !== 'object') {
		throw new Error('portfolio.json: projects.slugGroups missing');
	}
	const en = projects.en;
	if (!Array.isArray(en)) throw new Error('portfolio.json: projects.en must be an array');
	const bySlug = new Map();
	for (const entry of en) {
		if (entry && typeof entry.slug === 'string') bySlug.set(entry.slug, entry);
	}
	return { readme, bySlug };
}

function blurb(p) {
	if (typeof p.why === 'string' && p.why.length > 0) return p.why;
	if (typeof p.summary === 'string' && p.summary.length > 0) return p.summary;
	throw new Error(`portfolio.json: project "${p.slug}" needs "why" or "summary"`);
}

function lineFor(p, status) {
	const url = p.repoUrl;
	if (typeof url !== 'string' || !url.length) {
		throw new Error(`portfolio.json: project "${p.slug}" needs repoUrl for README sync`);
	}
	const title = p.title;
	if (typeof title !== 'string' || !title.length) {
		throw new Error(`portfolio.json: project "${p.slug}" needs title`);
	}
	const desc = blurb(p);
	const tech = typeof p.tech === 'string' && p.tech.length > 0 ? p.tech.toUpperCase() : 'PROJECT';
	return `- **[${title}](${url})** <sub>${status} / ${tech}</sub><br>${desc}\n`;
}

function buildProjectsBlock({ readme, bySlug }) {
	let out = '';
	for (let s = 0; s < SECTIONS.length; s++) {
		const { key, heading, status } = SECTIONS[s];
		const slugs = readme[key];
		if (!Array.isArray(slugs)) {
			throw new Error(`portfolio.json: projects.slugGroups.${key} must be an array of slugs`);
		}
		out += `${s === 0 ? '---\n\n' : ''}${heading}`;
		for (const slug of slugs) {
			const p = bySlug.get(slug);
			if (!p) throw new Error(`portfolio.json: slugGroups.${key} references unknown slug "${slug}"`);
			out += lineFor(p, status);
		}
		if (s < SECTIONS.length - 1) out += '\n';
	}
	return out;
}

function replaceBetween(src, start, end, inner) {
	const i0 = src.indexOf(start);
	const i1 = src.indexOf(end);
	if (i0 === -1 || i1 === -1 || i1 <= i0) {
		throw new Error(`README.md must contain ${start} and ${end} in that order`);
	}
	return `${src.slice(0, i0 + start.length)}\n${inner}${src.slice(i1)}`;
}

function main() {
	const portfolio = loadPortfolio();
	let readme = readFileSync(readmePath, 'utf8');
	const profileInner = buildReadmeProfile(portfolio);
	readme = replaceBetween(readme, PROFILE_START, PROFILE_END, profileInner);
	const projectsInner = buildProjectsBlock(loadProjectsPayload(portfolio));
	readme = replaceBetween(readme, PROJECTS_START, PROJECTS_END, `${projectsInner}`);
	const original = readFileSync(readmePath, 'utf8');
	if (readme !== original) writeFileSync(readmePath, readme, 'utf8');
}

main();
