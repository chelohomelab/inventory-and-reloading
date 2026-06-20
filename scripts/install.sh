#!/bin/bash
# Fresh server install / disaster recovery setup
# Run as root: bash /opt/inventory-and-reloading/scripts/install.sh

set -euo pipefail
APP_DIR="/opt/inventory-and-reloading"

echo "[install] Installing system dependencies..."
apt-get update -qq
apt-get install -y python3 python3-venv python3-pip git curl unzip

echo "[install] Setting up Python venv..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

echo "[install] Creating required directories..."
mkdir -p data static/uploads backups

echo "[install] Installing systemd service..."
cp "$APP_DIR/inventory.service" /etc/systemd/system/inventory.service
cp "$APP_DIR/inventory-backup.service" /etc/systemd/system/inventory-backup.service
cp "$APP_DIR/inventory-backup.timer" /etc/systemd/system/inventory-backup.timer
chmod 644 /etc/systemd/system/inventory*.service /etc/systemd/system/inventory*.timer
chmod +x "$APP_DIR/scripts/backup.sh"

echo "[install] Installing rclone..."
curl -s https://rclone.org/install.sh | bash

echo "[install] Enabling and starting services..."
systemctl daemon-reload
systemctl enable --now inventory
systemctl enable --now inventory-backup.timer

echo ""
echo "[install] Done! App running at http://$(hostname -I | awk '{print $1}'):8000"
echo ""
echo "Next steps:"
echo "  1. Go to /admin/backup and restore your backup ZIP"
echo "  2. Run: rclone config  — to set up cloud backup"
