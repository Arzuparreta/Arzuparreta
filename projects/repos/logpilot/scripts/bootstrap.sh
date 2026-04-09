#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

EMBEDDING_MODEL="${EMBEDDING_MODEL:-nomic-embed-text}"
CHAT_MODEL="${CHAT_MODEL:-llama3}"

if command -v ollama >/dev/null 2>&1; then
  echo "Pulling models with host Ollama CLI (ollama in PATH)..."
  ollama pull "${EMBEDDING_MODEL}"
  ollama pull "${CHAT_MODEL}"
  echo "Done."
  exit 0
fi

echo "error: ollama CLI not found in PATH." >&2
echo "Install Ollama on the host, or run pulls manually against your Ollama instance, e.g.:" >&2
echo "  curl -s http://127.0.0.1:11434/api/pull -d '{\"name\":\"${EMBEDDING_MODEL}\"}'" >&2
echo "  curl -s http://127.0.0.1:11434/api/pull -d '{\"name\":\"${CHAT_MODEL}\"}'" >&2
exit 1
