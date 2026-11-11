#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$ROOT/config/sensores.env" ]; then
  set -a
  source "$ROOT/config/sensores.env"
  set +a
else
  echo "Configuracion faltante. Ejecuta: ./scripts/install_sensores.sh"
  exit 1
fi
cd "$ROOT/robot"
exec python3 "$ROOT/robot/sds011_sensors_bridge.py"
