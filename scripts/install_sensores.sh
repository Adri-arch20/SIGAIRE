#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT/.venv/bin/uvicorn" ]; then
  echo "Instalando SALUD AMBIENTAL MeteoBot V7..."
  "$ROOT/scripts/install_raspberry.sh"
else
  echo "Actualizando frontend V7 y componentes de sensores..."
  cd "$ROOT/frontend"
  # Instalación limpia: evita node_modules de Windows y 'vite: Permission denied'.
  rm -rf node_modules dist
  if [ -f package-lock.json ]; then
    npm ci --no-audit --no-fund
  else
    npm install --no-audit --no-fund
  fi
  chmod +x node_modules/.bin/* 2>/dev/null || true
  npm run build
fi

echo "Comprobando dependencias SDS011..."
if ! python3 -c 'import serial, numpy' >/dev/null 2>&1; then
  sudo apt install -y python3-serial python3-numpy
fi

mkdir -p "$ROOT/config"
if [ ! -f "$ROOT/config/sensores.env" ]; then
  cp "$ROOT/config/sensores.env.example" "$ROOT/config/sensores.env"
  echo "Configuración creada: config/sensores.env"
else
  echo "Se conserva: config/sensores.env"
fi

python3 -m py_compile "$ROOT/robot/esp32_sensors_bridge.py" "$ROOT/robot/sds011_sensors_bridge.py" "$ROOT/robot/sds011_reader.py"

echo
echo "==============================================="
echo " SALUD AMBIENTAL V7.2 - SENSORES ESP32 + SDS011 + MG811 PREPARADOS"
echo "==============================================="
echo "ESP32 predeterminada: 192.168.137.200"
echo "Inicia WEB + ESP32 + SDS011 con: ./scripts/start_salud_ambiental_sensores.sh"
