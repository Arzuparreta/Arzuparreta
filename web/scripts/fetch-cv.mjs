#!/usr/bin/env node
/**
 * Optionally downloads CV.md from github.com/Arzuparreta/CV before build.
 * Default build uses SKIP_FETCH_CV=1 and the committed public/resume/CV.md.
 * @see https://github.com/Arzuparreta/CV
 */
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const OUT = join(ROOT, 'public', 'resume', 'CV.md');
const CV_RAW_URL =
	process.env.CV_RAW_URL ??
	'https://raw.githubusercontent.com/Arzuparreta/CV/main/CV.md';

const MAX_ATTEMPTS = 3;
const RETRY_MS = 1500;

async function sleep(ms) {
	return new Promise((r) => setTimeout(r, ms));
}

async function fetchWithRetries() {
	let lastErr;
	for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt++) {
		try {
			const res = await fetch(CV_RAW_URL, {
				headers: { Accept: 'text/markdown, text/plain, */*' },
				redirect: 'follow',
			});
			if (!res.ok) {
				throw new Error(`HTTP ${res.status} ${res.statusText}`);
			}
			const text = await res.text();
			if (!text.trim()) {
				throw new Error('Empty response body');
			}
			return text;
		} catch (e) {
			lastErr = e;
			console.warn(`fetch-cv: attempt ${attempt}/${MAX_ATTEMPTS} failed:`, e.message);
			if (attempt < MAX_ATTEMPTS) await sleep(RETRY_MS * attempt);
		}
	}
	throw new Error(`fetch-cv: failed after ${MAX_ATTEMPTS} attempts: ${lastErr?.message ?? lastErr}`);
}

async function main() {
	if (process.env.SKIP_FETCH_CV === '1') {
		console.warn('fetch-cv: SKIP_FETCH_CV=1 — skipping download (ensure public/resume/CV.md exists locally).');
		return;
	}

	const text = await fetchWithRetries();
	await mkdir(dirname(OUT), { recursive: true });
	await writeFile(OUT, text, 'utf8');
	console.log(`fetch-cv: wrote ${OUT} (${text.length} bytes) from ${CV_RAW_URL}`);
}

main().catch((err) => {
	console.error(err);
	process.exit(1);
});
