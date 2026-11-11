#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
SERVICE="/etc/systemd/system/sigaire.service"

if [ ! -x "$ROOT/.venv/bin/uvicorn" ]; then
  echo "Ejecuta primero scripts/install_raspberry.sh"
  exit 1
fi

sudo tee "$SERVICE" >/dev/null <<EOF
[Unit]
Description=SIGAIRE - MeteoBot IoT autonomo
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$ROOT
Environment=SIGAIRE_STORE_INTERVAL=1.0
ExecStart=$ROOT/.venv/bin/uvicorn app.main:app --app-dir $ROOT/backend --host 0.0.0.0 --port 5000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable sigaire
sudo systemctl restart sigaire

echo
echo "Servicio instalado."
echo "Estado:"
systemctl --no-pager --full status sigaire || true
