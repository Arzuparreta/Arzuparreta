#!/usr/bin/env node
/**
 * Copies canonical CV from monorepo root (../cv/CV.md) into public/resume/CV.md for Astro.
 */
import { copyFileSync, mkdirSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(__dirname, '..');
const REPO_ROOT = join(WEB_ROOT, '..');
const SRC = join(REPO_ROOT, 'cv', 'CV.md');
const DEST = join(WEB_ROOT, 'public', 'resume', 'CV.md');

if (!existsSync(SRC)) {
	console.error(`ensure-cv: missing ${SRC} (expected monorepo layout: cv/CV.md next to web/).`);
	process.exit(1);
}

mkdirSync(dirname(DEST), { recursive: true });
copyFileSync(SRC, DEST);
console.log(`ensure-cv: copied ${SRC} -> ${DEST}`);
