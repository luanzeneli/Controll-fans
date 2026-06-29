#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
if ! pgrep -x openrgb >/dev/null; then
  echo "Starting OpenRGB SDK server..."
  openrgb --server --noautoconnect >/dev/null 2>&1 &
  sleep 2
fi
if [ -x "$DIR/.venv/bin/python" ]; then
  PY="$DIR/.venv/bin/python"
else
  PY="python3"
fi
exec "$PY" -m src.app
