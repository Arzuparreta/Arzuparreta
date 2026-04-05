#!/usr/bin/env node
/**
 * Copies canonical project data from monorepo root (../projects/projects.json) into public/data/projects.json for Astro and static download.
 */
import { copyFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(__dirname, '..');
const REPO_ROOT = join(WEB_ROOT, '..');
const SRC = join(REPO_ROOT, 'projects', 'projects.json');
const DEST = join(WEB_ROOT, 'public', 'data', 'projects.json');

if (!existsSync(SRC)) {
	console.error(`ensure-projects: missing ${SRC} (expected monorepo layout: projects/projects.json next to web/).`);
	process.exit(1);
}

mkdirSync(dirname(DEST), { recursive: true });
copyFileSync(SRC, DEST);
console.log(`ensure-projects: copied ${SRC} -> ${DEST}`);
