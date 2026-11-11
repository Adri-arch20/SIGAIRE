#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "============================================"
echo " SALUD AMBIENTAL MeteoBot V7 - Raspberry Pi 5"
echo "============================================"
echo "Proyecto: $ROOT"
echo

sudo apt update
sudo apt install -y \
  python3-venv \
  python3-serial \
  python3-numpy \
  python3-opencv \
  python3-picamera2 \
  python3-requests \
  nodejs \
  npm

echo
echo "[1/3] Backend FastAPI"
if [ ! -d "$ROOT/.venv" ]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/backend/requirements.txt"

echo
echo "[2/3] Frontend Vue 3 - instalacion limpia para Raspberry Pi"
cd "$ROOT/frontend"
# Evita el problema 'vite: Permission denied' y binarios de node_modules copiados desde Windows.
rm -rf node_modules dist
if [ -f package-lock.json ]; then
  npm ci --no-audit --no-fund
else
  npm install --no-audit --no-fund
fi
chmod +x node_modules/.bin/* 2>/dev/null || true
npm run build

echo
echo "[3/3] Almacenamiento y configuración"
mkdir -p "$ROOT/backend/data" "$ROOT/config"
if [ ! -f "$ROOT/config/sensores.env" ]; then
  cp "$ROOT/config/sensores.env.example" "$ROOT/config/sensores.env"
fi

echo
echo "============================================"
echo " SALUD AMBIENTAL MeteoBot V7 instalado"
echo "============================================"
echo "Web:      $ROOT/scripts/run.sh"
echo "Sensores: $ROOT/scripts/start_salud_ambiental_sensores.sh"
echo "Robot:    $ROOT/scripts/run_robot_autonomo.sh"
echo "URL:      http://IP_DE_TU_RASPBERRY:5000/"
