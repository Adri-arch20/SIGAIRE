#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
if [ ! -f "$ROOT/config/sensores.env" ]; then
  echo "Primero ejecuta: ./scripts/install_sensores.sh"
  exit 1
fi
"$ROOT/scripts/install_systemd.sh"

sudo tee /etc/systemd/system/sigaire-sensores.service >/dev/null <<EOF_SERVICE
[Unit]
Description=SIGAIRE - puente de sensores ESP32
After=network-online.target sigaire.service
Wants=network-online.target sigaire.service

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$ROOT
EnvironmentFile=$ROOT/config/sensores.env
ExecStart=/usr/bin/python3 $ROOT/robot/esp32_sensors_bridge.py
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF_SERVICE
sudo systemctl daemon-reload
sudo systemctl enable --now sigaire-sensores.service
systemctl --no-pager --full status sigaire-sensores.service || true
