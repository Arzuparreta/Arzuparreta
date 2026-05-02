/**
 * Regenerates the GitHub profile README project block from projects/projects.json.
 * Edit only projects.json (and the static "Currently focused on" section above the markers in README.md).
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const projectsPath = join(root, 'projects', 'projects.json');
const readmePath = join(root, 'README.md');

const START = '<!-- readme-projects:start -->';
const END = '<!-- readme-projects:end -->';

const SECTIONS = [
	{
		key: 'actively',
		heading: '### 🚧 Actively developing:\n',
		boldLink: true,
	},
	{
		key: 'maintaining',
		heading: '### 🛠️ Maintaining / improving:\n',
		boldLink: true,
	},
	{
		key: 'minor',
		heading: '#### 🗃️ Out of focus / unmaintained:\n',
		boldLink: false,
	},
];

function loadJson() {
	const raw = readFileSync(projectsPath, 'utf8');
	const data = JSON.parse(raw);
	const readme = data.readme;
	if (readme === null || typeof readme !== 'object') {
		throw new Error('projects.json: missing "readme" object');
	}
	const en = data.en;
	if (!Array.isArray(en)) throw new Error('projects.json: "en" must be an array');
	const bySlug = new Map();
	for (const entry of en) {
		if (entry && typeof entry.slug === 'string') bySlug.set(entry.slug, entry);
	}
	return { readme, bySlug };
}

function blurb(p) {
	if (typeof p.why === 'string' && p.why.length > 0) return p.why;
	if (typeof p.summary === 'string' && p.summary.length > 0) return p.summary;
	throw new Error(`projects.json: entry "${p.slug}" needs "why" or "summary"`);
}

function lineFor(p, boldLink, sectionKey) {
	const url = p.repoUrl;
	if (typeof url !== 'string' || !url.length) {
		throw new Error(`projects.json: entry "${p.slug}" needs repoUrl for README sync`);
	}
	const title = p.title;
	if (typeof title !== 'string' || !title.length) {
		throw new Error(`projects.json: entry "${p.slug}" needs title`);
	}
	const desc = blurb(p);
	const emoji = typeof p.readmeEmoji === 'string' ? p.readmeEmoji : '';
	if (boldLink) {
		if (emoji) {
			const spacer = sectionKey === 'actively' ? ` ${emoji} : ` : ` ${emoji}: `;
			return `- [**${title}**](${url})${spacer}${desc}\n`;
		}
		return `- [**${title}**](${url}): ${desc}\n`;
	}
	return `- [${title}](${url}): ${desc}\n`;
}

function buildBlock({ readme, bySlug }) {
	let out = '';
	for (let s = 0; s < SECTIONS.length; s++) {
		const { key, heading, boldLink } = SECTIONS[s];
		const slugs = readme[key];
		if (!Array.isArray(slugs)) {
			throw new Error(`projects.json: readme.${key} must be an array of slugs`);
		}
		out += heading;
		for (const slug of slugs) {
			const p = bySlug.get(slug);
			if (!p) throw new Error(`projects.json: readme.${key} references unknown slug "${slug}"`);
			out += lineFor(p, boldLink, key);
		}
		if (s < SECTIONS.length - 1) out += '\n';
	}
	return out;
}

function main() {
	const readme = readFileSync(readmePath, 'utf8');
	const i0 = readme.indexOf(START);
	const i1 = readme.indexOf(END);
	if (i0 === -1 || i1 === -1 || i1 <= i0) {
		throw new Error(`README.md must contain ${START} and ${END} in that order`);
	}
	const inner = buildBlock(loadJson());
	const before = readme.slice(0, i0 + START.length);
	const after = readme.slice(i1);
	const next = `${before}\n${inner}${after}`;
	if (next !== readme) writeFileSync(readmePath, next, 'utf8');
}

main();
