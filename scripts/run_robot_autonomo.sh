#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT="$ROOT/robot/meteobot_autonomo_yolo_sds011_sigaire.py"

cd "$ROOT/robot"

if [ -x "$ROOT/.robot-venv/bin/python" ]; then
  exec "$ROOT/.robot-venv/bin/python" "$SCRIPT"
fi

exec python3 "$SCRIPT"
