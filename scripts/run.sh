#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT/.venv/bin/uvicorn" ]; then
  echo "Faltan dependencias de SALUD AMBIENTAL."
  echo "Ejecuta primero: $ROOT/scripts/install_raspberry.sh"
  exit 1
fi

cd "$ROOT"

exec "$ROOT/.venv/bin/uvicorn" \
  app.main:app \
  --app-dir "$ROOT/backend" \
  --host 0.0.0.0 \
  --port 5000
