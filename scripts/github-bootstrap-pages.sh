#!/usr/bin/env bash
# Deploy web/dist to Arzuparreta.github.io gh-pages, switch Pages to branch (legacy) build,
# set GH_PAGES_DEPLOY_TOKEN on Arzuparreta/Arzuparreta, remove artifact deploy workflow from .github.io.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$REPO_ROOT/web"
VENV="$REPO_ROOT/.tools/venv/bin/python"
if [[ ! -x "$VENV" ]]; then
	echo "Missing $VENV — run: python3 -m venv .tools/venv && .tools/venv/bin/pip install PyNaCl"
	exit 1
fi

GHIO="Arzuparreta/Arzuparreta.github.io"
MONO="Arzuparreta/Arzuparreta"

line="$(grep -E 'https://.*github\.com' "${HOME}/.git-credentials" 2>/dev/null | head -1 || true)"
if [[ -z "$line" ]]; then
	echo "No github.com HTTPS credentials in ~/.git-credentials."
	exit 1
fi
TOKEN="$(printf '%s\n' "$line" | sed -n 's|https://[^:]*:\([^@]*\)@github.com|\1|p')"
GITHUB_USER="$(printf '%s\n' "$line" | sed -n 's|https://\([^:]*\):.*@github.com|\1|p')"
if [[ -z "$TOKEN" || -z "$GITHUB_USER" ]]; then
	echo "Could not parse token/user from ~/.git-credentials"
	exit 1
fi

AUTH_HEADER="Authorization: Bearer ${TOKEN}"
API=(curl -sS -H "Accept: application/vnd.github+json" -H "${AUTH_HEADER}" -H "X-GitHub-Api-Version: 2022-11-28")

put_actions_secret() {
	local repo_full="$1"
	local name="$2"
	local value="$3"
	local owner="${repo_full%%/*}"
	local repo="${repo_full#*/}"
	local key_json key_id key_b64 enc payload code http_body
	key_json="$("${API[@]}" "https://api.github.com/repos/${owner}/${repo}/actions/secrets/public-key")"
	key_id="$(printf '%s' "$key_json" | "$VENV" -c "import sys,json; print(json.load(sys.stdin)['key_id'])")"
	key_b64="$(printf '%s' "$key_json" | "$VENV" -c "import sys,json; print(json.load(sys.stdin)['key'])")"
	enc="$(KEY_B64="$key_b64" VALUE="$value" "$VENV" - <<'PY'
import base64, json, os
from nacl import public

raw = base64.b64decode(os.environ["KEY_B64"])
pk = public.PublicKey(raw)
box = public.SealedBox(pk)
out = box.encrypt(os.environ["VALUE"].encode())
print(base64.b64encode(out).decode())
PY
)"
	payload="$(KEY_ID="$key_id" ENC="$enc" "$VENV" - <<'PY'
import json, os
print(json.dumps({"key_id": os.environ["KEY_ID"], "encrypted_value": os.environ["ENC"]}))
PY
)"
	http_body="$(curl -sS -w "\n%{http_code}" -X PUT \
		-H "Accept: application/vnd.github+json" \
		-H "${AUTH_HEADER}" \
		-H "X-GitHub-Api-Version: 2022-11-28" \
		-H "Content-Type: application/json" \
		-d "$payload" \
		"https://api.github.com/repos/${owner}/${repo}/actions/secrets/${name}")"
	code="$(printf '%s' "$http_body" | tail -n1)"
	if [[ "$code" != "201" && "$code" != "204" ]]; then
		echo "Failed to set secret ${name} on ${repo_full}: HTTP ${code}"
		printf '%s' "$http_body" | head -n -1
		exit 1
	fi
	echo "Set Actions secret ${name} on ${repo_full} (HTTP ${code})"
}

echo "== Build Astro site =="
(cd "$WEB" && npm ci --silent && npm run build)

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -a "$WEB/dist/." "$STAGE/"

echo "== Push gh-pages to ${GHIO} =="
cd "$STAGE"
git init -b gh-pages
git config user.email "${GITHUB_USER}@users.noreply.github.com"
git config user.name "${GITHUB_USER}"
git add -A
git commit -m "Deploy static site from ${MONO} monorepo"
git remote add origin "https://${GITHUB_USER}:${TOKEN}@github.com/${GHIO}.git"
GIT_TERMINAL_PROMPT=0 git push -f origin gh-pages

echo "== Switch GitHub Pages to legacy / gh-pages =="
body='{"build_type":"legacy","source":{"branch":"gh-pages","path":"/"}}'
http_body="$(curl -sS -w "\n%{http_code}" -X PUT \
	-H "Accept: application/vnd.github+json" \
	-H "${AUTH_HEADER}" \
	-H "X-GitHub-Api-Version: 2022-11-28" \
	-H "Content-Type: application/json" \
	-d "$body" \
	"https://api.github.com/repos/${GHIO}/pages")"
code="$(printf '%s' "$http_body" | tail -n1)"
if [[ "$code" != "204" ]]; then
	echo "Pages PUT returned HTTP ${code}"
	printf '%s' "$http_body" | head -n -1
	exit 1
fi
echo "Pages source updated (HTTP 204)."

echo "== Store PAT as GH_PAGES_DEPLOY_TOKEN on ${MONO} =="
put_actions_secret "$MONO" "GH_PAGES_DEPLOY_TOKEN" "$TOKEN"

echo "== Remove old workflow from ${GHIO} main =="
TMPGIT="$(mktemp -d)"
git clone --depth 1 "https://${GITHUB_USER}:${TOKEN}@github.com/${GHIO}.git" "$TMPGIT/ghio"
cd "$TMPGIT/ghio"
if [[ -f .github/workflows/deploy.yml ]]; then
	git rm -f .github/workflows/deploy.yml
	git config user.email "${GITHUB_USER}@users.noreply.github.com"
	git config user.name "${GITHUB_USER}"
	git commit -m "Stop Actions artifact deploy; site is published from gh-pages (built in ${MONO})"
	git push origin main
	echo "Removed deploy.yml from ${GHIO} main."
else
	echo "deploy.yml already absent."
fi
rm -rf "$TMPGIT"

echo "Done. Pushes to ${MONO} on main will deploy via Actions."
