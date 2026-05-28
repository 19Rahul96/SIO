#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/backend"

if [[ -f ".venv/bin/activate" ]]; then
  source .venv/bin/activate
elif [[ -f "venv/bin/activate" ]]; then
  source venv/bin/activate
fi

exec uvicorn --app-dir "$(pwd)" main:app --reload \
  --reload-exclude "data/*" \
  --reload-exclude "__pycache__/*" \
  --host 0.0.0.0 --port 8010
