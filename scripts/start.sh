#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

[[ -x .venv/bin/uvicorn ]] || { printf 'Run ./scripts/setup.sh first.\n' >&2; exit 1; }
[[ -x node_modules/.bin/vite ]] || { printf 'Run ./scripts/setup.sh first.\n' >&2; exit 1; }
[[ -f backend/models/crop_classifier.onnx && -f backend/models/metadata.json ]] || {
  printf 'The trained crop classifier is missing. Re-clone the complete repository or restore backend/models.\n' >&2
  exit 1
}

OLLAMA_URL="http://127.0.0.1:11434"
if ! curl --silent --fail --max-time 2 "$OLLAMA_URL/api/tags" >/dev/null; then
  printf 'Ollama is not responding at %s. Run ./scripts/setup.sh to install/start it and pull the model.\n' "$OLLAMA_URL" >&2
  exit 1
fi

MODEL="${AGRI_LLM_MODEL:-gemma3:4b}"
if ! ollama list | awk -v model="$MODEL" 'NR > 1 && $1 == model { found = 1 } END { exit !found }'; then
  printf 'Ollama model %s is missing. Run ./scripts/setup.sh to download it.\n' "$MODEL" >&2
  exit 1
fi

export AGRI_LLM_MODEL="$MODEL"
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!
./node_modules/.bin/vite --host 127.0.0.1 &
WEB_PID=$!

cleanup() {
  trap - EXIT INT TERM
  kill "$API_PID" "$WEB_PID" 2>/dev/null || true
  wait "$API_PID" "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

printf 'Uzhavan is starting. Open http://127.0.0.1:5173 (API: http://127.0.0.1:8000).\nPress Ctrl+C to stop both app servers.\n'

READY=0
for _ in $(seq 1 30); do
  if curl --silent --fail --max-time 2 http://127.0.0.1:8000/api/health >/dev/null \
    && curl --silent --fail --max-time 2 http://127.0.0.1:5173/ >/dev/null; then
    READY=1
    break
  fi
  if ! kill -0 "$API_PID" 2>/dev/null || ! kill -0 "$WEB_PID" 2>/dev/null; then
    break
  fi
  sleep 1
done

if [[ "$READY" != "1" ]]; then
  printf 'Uzhavan did not become ready. Review the server output above and retry after fixing the reported error.\n' >&2
  exit 1
fi

printf 'Uzhavan is ready at http://127.0.0.1:5173.\n'

while kill -0 "$API_PID" 2>/dev/null && kill -0 "$WEB_PID" 2>/dev/null; do
  sleep 1
done

printf 'A Uzhavan server stopped unexpectedly; stopping the other server.\n' >&2
exit 1
