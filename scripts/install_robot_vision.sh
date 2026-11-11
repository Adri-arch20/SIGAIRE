#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="$ROOT/.robot-venv"

echo "============================================"
echo " SALUD AMBIENTAL MeteoBot v7 - Vision autonoma / YOLO"
echo "============================================"

sudo apt update
sudo apt install -y \
  python3-venv \
  python3-picamera2 \
  python3-opencv \
  python3-numpy \
  python3-requests \
  python3-serial

if [ ! -d "$VENV" ]; then
  python3 -m venv --system-site-packages "$VENV"
fi

"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install --upgrade -r "$ROOT/robot/requirements_vision.txt"

mkdir -p "$ROOT/robot/models"

echo
echo "Vision instalada."
echo "El script usa por defecto yolo11n.pt."
echo "Ultralytics puede descargarlo en el primer arranque si hay Internet."
echo "Tambien puedes copiar tu modelo a robot/models/ y ejecutar:"
echo "  METEOBOT_YOLO_MODEL=$ROOT/robot/models/tu_modelo.pt ./scripts/run_robot_autonomo.sh"
