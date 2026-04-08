#!/usr/bin/env bash
# Setup script for Hokidraw Bot on Ubuntu VPS
set -e

INSTALL_DIR="/opt/hokidraw-bot"
SERVICE_NAME="hokidraw-bot"

echo "=== Hokidraw Bot Setup ==="

# ── System deps
sudo apt-get update -qq
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev build-essential libssl-dev

# ── Install dir
sudo mkdir -p "$INSTALL_DIR"
sudo chown "$USER:$USER" "$INSTALL_DIR"

# ── Copy files
cp -r . "$INSTALL_DIR/"
cd "$INSTALL_DIR"

# ── Python venv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# ── Playwright browsers (optional, for Cloudflare bypass)
python -m playwright install chromium --with-deps || echo "Playwright install skipped"

# ── Directories
mkdir -p data logs

# ── .env from example if not present
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo ">>> Edit .env and fill in your credentials before starting! <<<"
    echo "    nano $INSTALL_DIR/.env"
fi

# ── Systemd service
sudo cp "$INSTALL_DIR/hokidraw-bot.service" /etc/systemd/system/
sudo sed -i "s|/opt/hokidraw-bot|$INSTALL_DIR|g" /etc/systemd/system/hokidraw-bot.service
sudo systemctl daemon-reload

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit credentials:    nano $INSTALL_DIR/.env"
echo "  2. Test dry-run:        cd $INSTALL_DIR && source venv/bin/activate && python main.py --dry-run"
echo "  3. Enable service:      sudo systemctl enable --now $SERVICE_NAME"
echo "  4. Check status:        sudo systemctl status $SERVICE_NAME"
echo "  5. View logs:           journalctl -u $SERVICE_NAME -f"
