// @ts-check
import { defineConfig } from 'astro/config';
import { copyFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// User site: https://arzuparreta.github.io — served at repository root (base: '/')
// https://docs.astro.build/en/guides/deploy/github/
export default defineConfig({
	site: 'https://arzuparreta.github.io',
	base: '/',
	output: 'static',
	compressHTML: true,
	integrations: [
		{
			name: 'ensure-robots-txt',
			hooks: {
				/** @param {{ dir: URL }} opts */
				'astro:build:done': ({ dir }) => {
					const targetDir = fileURLToPath(dir);
					const robots = join(__dirname, 'public', 'robots.txt');
					if (existsSync(robots)) {
						copyFileSync(robots, join(targetDir, 'robots.txt'));
					}
				},
			},
		},
	],
});
