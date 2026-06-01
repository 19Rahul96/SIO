#!/usr/bin/env bash
# Stop the Semantic Intelligence OS service started by start_sio.sh.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${SIO_PORT:-8020}"
pidfile="$ROOT/.sio/service.pid"
if [ -f "$pidfile" ]; then
  pid="$(cat "$pidfile")"
  kill "$pid" 2>/dev/null && echo "[sio] stopped service (pid $pid)" || echo "[sio] service pid $pid not running"
  rm -f "$pidfile"
fi
# Fallback: free the port if anything lingers (covers servers started another way).
fuser -k "${PORT}/tcp" 2>/dev/null || true
echo "[sio] done"
