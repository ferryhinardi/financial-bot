#!/bin/bash
# ──────────────────────────────────────────────────
# Oracle Cloud VM Setup Script
# Run this on your Oracle Cloud Ubuntu VM
# ──────────────────────────────────────────────────

set -e

echo "=================================="
echo " Financial Bot - Oracle Cloud Setup"
echo "=================================="

# 1. Update system
echo "[1/6] Updating system..."
sudo apt update && sudo apt upgrade -y

# 2. Install Python & pip
echo "[2/6] Installing Python..."
sudo apt install -y python3 python3-pip python3-venv git

# 3. Clone or copy project
echo "[3/6] Setting up project..."
APP_DIR="$HOME/financial-bot"
if [ ! -d "$APP_DIR" ]; then
    mkdir -p "$APP_DIR"
    echo "Created $APP_DIR"
    echo "Please copy your project files to $APP_DIR"
    echo "You can use scp:"
    echo "  scp -r ~/Workspace/financial-bot/* user@<VM_IP>:~/financial-bot/"
fi
cd "$APP_DIR"

# 4. Setup Python environment
echo "[4/6] Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Generate Excel if not exists
if [ ! -f "Financial_Tracker.xlsx" ]; then
    echo "[5/6] Generating Financial Tracker spreadsheet..."
    python create_financial_tracker.py
else
    echo "[5/6] Financial_Tracker.xlsx already exists, skipping."
fi

# 6. Setup .env if not exists
if [ ! -f ".env" ]; then
    echo "[6/6] Creating .env file..."
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Edit .env with your bot token:"
    echo "  nano $APP_DIR/.env"
    echo ""
else
    echo "[6/6] .env already exists."
fi

# 7. Setup systemd service
echo ""
echo "Setting up auto-start service..."
sudo tee /etc/systemd/system/financial-bot.service > /dev/null << SERVICEEOF
[Unit]
Description=Financial Tracker Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/bot.py
Restart=always
RestartSec=10
Environment=PATH=$APP_DIR/venv/bin:/usr/bin:/bin

[Install]
WantedBy=multi-user.target
SERVICEEOF

sudo systemctl daemon-reload
sudo systemctl enable financial-bot.service

echo ""
echo "=================================="
echo " Setup Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env:        nano $APP_DIR/.env"
echo "  2. Start the bot:    sudo systemctl start financial-bot"
echo "  3. Check status:     sudo systemctl status financial-bot"
echo "  4. View logs:        sudo journalctl -u financial-bot -f"
echo ""
echo "Other commands:"
echo "  Stop:                sudo systemctl stop financial-bot"
echo "  Restart:             sudo systemctl restart financial-bot"
echo "  Disable auto-start:  sudo systemctl disable financial-bot"
echo ""
