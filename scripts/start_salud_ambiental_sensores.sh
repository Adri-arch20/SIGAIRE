#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -f "$ROOT/config/sensores.env" ]; then
  echo "Falta config/sensores.env"
  echo "Ejecuta primero: ./scripts/install_sensores.sh"
  exit 1
fi

WEB_PID=""
ESP32_PID=""
SDS_PID=""
cleanup() {
  echo "Deteniendo SALUD AMBIENTAL y puentes de sensores..."
  [ -z "$SDS_PID" ] || kill "$SDS_PID" 2>/dev/null || true
  [ -z "$ESP32_PID" ] || kill "$ESP32_PID" 2>/dev/null || true
  [ -z "$WEB_PID" ] || kill "$WEB_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$ROOT/scripts/run.sh" & WEB_PID=$!
sleep 2
if ! kill -0 "$WEB_PID" 2>/dev/null; then
  echo "La web no inicio. Verifica el puerto 5000."
  exit 1
fi

"$ROOT/scripts/run_sensors_bridge.sh" & ESP32_PID=$!
"$ROOT/scripts/run_sds011_bridge.sh" & SDS_PID=$!

echo
echo "SALUD AMBIENTAL MeteoBot V7.2"
echo "Web:   http://IP_DE_TU_RASPBERRY:5000/"
echo "ESP32: $(grep '^METEOBOT_ESP32_IP=' "$ROOT/config/sensores.env" | cut -d= -f2-)"
echo "SDS011: puente PM2.5/PM10 iniciado"
echo "Procesos activos: WEB + ESP32 + SDS011"
echo "Ctrl+C detiene los tres procesos."
wait -n "$WEB_PID" "$ESP32_PID" "$SDS_PID"
