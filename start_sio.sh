#!/usr/bin/env bash
# Host the Semantic Intelligence OS as a SINGLE persistent service.
# One FastAPI process serves BOTH the 14-layer pipeline API and the built React SPA
# (interactive knowledge graph + EDA/trust/governance/metadata/ontology visuals).
#
#   Open: http://127.0.0.1:8020/   ->   "◆ Semantic OS" tab
#   (API docs at /docs, health at /health)
#
# Usage:
#   ./start_sio.sh           # build frontend if needed, then serve
#   ./start_sio.sh --build   # force a fresh frontend build first
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UVICORN="$ROOT/venv/bin/uvicorn"
PORT="${SIO_PORT:-8020}"
mkdir -p "$ROOT/.sio"

if [[ "${1:-}" == "--build" || ! -f "$ROOT/frontend/dist/index.html" ]]; then
  echo "[sio] building frontend bundle ..."
  ( cd "$ROOT/frontend" && npm run build )
fi

# Free the port if something is already bound there.
fuser -k "${PORT}/tcp" 2>/dev/null || true
sleep 1

echo "[sio] starting service on 0.0.0.0:${PORT} ..."
# setsid + nohup + disown => fully detached; survives this shell closing.
cd "$ROOT/semantic_intelligence_os"
setsid nohup "$UVICORN" app.main:app --host 0.0.0.0 --port "$PORT" \
  > "$ROOT/.sio/service.log" 2>&1 < /dev/null &
echo $! > "$ROOT/.sio/service.pid"
disown || true

sleep 4
code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/health" || echo down)"
echo "[sio] health  : ${code}"
echo "[sio] open    : http://127.0.0.1:${PORT}/"
echo "[sio] log     : $ROOT/.sio/service.log"
echo "[sio] stop    : ./stop_sio.sh"
