#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB="$ROOT/backend/data/singare.db"
BACKUP_DIR="$ROOT/backups"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB" ]; then
  echo "Todavia no existe la base de datos: $DB"
  exit 1
fi

STAMP="$(date +%Y-%m-%d_%H-%M-%S)"
DEST="$BACKUP_DIR/sigaire_$STAMP.db"

cp "$DB" "$DEST"

echo "Backup creado:"
echo "$DEST"
