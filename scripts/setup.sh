#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

fail() {
  printf 'Setup failed: %s\n' "$1" >&2
  exit 1
}

if [[ "$(uname -s)" != "Darwin" ]]; then
  fail "This automatic installer currently supports macOS. Install Python 3.11+, Node.js 22+, npm, Ollama, and Git separately on other systems, then rerun this script."
fi

command -v brew >/dev/null 2>&1 || fail "Homebrew is required. Install it from https://brew.sh, then rerun ./scripts/setup.sh."

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
  brew install python@3.12
  export PATH="$(brew --prefix python@3.12)/bin:$PATH"
fi

if ! command -v node >/dev/null 2>&1 || ! node -e 'const [major, minor] = process.versions.node.split(".").map(Number); process.exit(major < 22 || (major === 22 && minor < 12) ? 1 : 0)'; then
  brew install node@22
  export PATH="$(brew --prefix node@22)/bin:$PATH"
fi

command -v npm >/dev/null 2>&1 || fail "npm was not found after installing Node.js."

if ! command -v ollama >/dev/null 2>&1; then
  brew install ollama
fi

if [[ ! -x .venv/bin/python ]]; then
  printf 'Creating the Python virtual environment...\n'
  python3 -m venv .venv
fi

printf 'Installing backend Python dependencies...\n'
export PIP_DISABLE_PIP_VERSION_CHECK=1
.venv/bin/python -m pip install -r requirements.txt
printf 'Installing locked frontend dependencies...\n'
npm ci

if [[ ! -f backend/models/crop_classifier.onnx || ! -f backend/models/metadata.json ]]; then
  fail "The trained crop classifier or its metadata is missing from backend/models."
fi

if [[ ! -f .env.local ]]; then
  cp .env.example .env.local
  printf 'Created .env.local from .env.example. Add Firebase project values only if you need Firebase sign-in and cloud sync.\n'
fi

OLLAMA_URL="http://127.0.0.1:11434"
if ! curl --silent --fail --max-time 2 "$OLLAMA_URL/api/tags" >/dev/null; then
  OLLAMA_LOG="${TMPDIR:-/tmp}/uzhavan-ollama.log"
  printf 'Starting the Ollama service...\n'
  ollama serve >"$OLLAMA_LOG" 2>&1 &
  OLLAMA_PID=$!
  READY=0
  for _ in $(seq 1 30); do
    if curl --silent --fail --max-time 2 "$OLLAMA_URL/api/tags" >/dev/null; then
      READY=1
      break
    fi
    if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
      break
    fi
    sleep 1
  done
  if [[ "$READY" != "1" ]]; then
    fail "Ollama did not start. Check $OLLAMA_LOG and start Ollama before retrying."
  fi
fi

MODEL="${AGRI_LLM_MODEL:-gemma3:4b}"
printf 'Checking/downloading the local chat model (%s)...\n' "$MODEL"
ollama pull "$MODEL"

printf '\nSetup complete. Start Uzhavan with: ./scripts/start.sh\n'
