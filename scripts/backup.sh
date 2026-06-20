#!/bin/bash
# Inventory & Reloading — backup script
# Run by systemd inventory-backup.timer (daily)
# Can also be run manually: bash /opt/inventory-and-reloading/scripts/backup.sh

set -euo pipefail
APP_DIR="/opt/inventory-and-reloading"
cd "$APP_DIR"
source venv/bin/activate 2>/dev/null || true

python3 "$APP_DIR/scripts/backup.py"
