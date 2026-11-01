#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv. Follow the one-time setup in README.md first."
  exit 1
fi

if [[ ! -d "frontend/node_modules" ]]; then
  echo "Missing frontend dependencies. Run: cd frontend && npm install"
  exit 1
fi

.venv/bin/python scripts/generate_demo_data.py
(cd frontend && npm run build)

echo "Starting ProofLedger AI at http://127.0.0.1:8000"
exec .venv/bin/python -m uvicorn backend.app.main:app --host "${API_HOST:-127.0.0.1}" --port "${API_PORT:-8000}"
