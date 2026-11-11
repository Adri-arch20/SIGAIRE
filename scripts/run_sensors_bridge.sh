#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ -f "$ROOT/config/sensores.env" ]; then
  set -a
  # Archivo local editable (no descargar de fuentes externas).
  source "$ROOT/config/sensores.env"
  set +a
else
  echo "Configuracion faltante. Ejecuta: ./scripts/install_sensores.sh"
  exit 1
fi
cd "$ROOT"
exec python3 "$ROOT/robot/esp32_sensors_bridge.py"
