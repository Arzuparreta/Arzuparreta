#!/usr/bin/env sh
# Install repo-local Git hooks (pre-push → make check). Idempotent.
set -e
ROOT=$(git rev-parse --show-toplevel 2>/dev/null) || {
  echo "logpilot: run from inside a git repository" >&2
  exit 1
}
cd "$ROOT" || exit 1
git config core.hooksPath .githooks
chmod +x .githooks/pre-push 2>/dev/null || true
echo "logpilot: core.hooksPath=.githooks (pre-push runs make check; skip with LOGPILOT_SKIP_HOOKS=1)"
