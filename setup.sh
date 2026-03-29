#!/bin/bash
# ──────────────────────────────────────────────────
# Financial Tracker Bot - Setup Script
# ──────────────────────────────────────────────────

set -e

echo "=================================="
echo " Financial Tracker Bot - Setup"
echo "=================================="
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is required. Install it first."
    exit 1
fi

echo "[1/4] Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "[2/4] Installing dependencies..."
pip install -r requirements.txt --quiet

echo "[3/4] Setting up configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "IMPORTANT: Edit .env file with your settings:"
    echo "  1. Get a Telegram bot token from @BotFather"
    echo "  2. Set TELEGRAM_BOT_TOKEN in .env"
    echo "  3. Verify EXCEL_PATH points to your Financial_Tracker.xlsx"
    echo ""
    echo "  nano $SCRIPT_DIR/.env"
    echo ""
else
    echo "  .env already exists, skipping."
fi

echo "[4/4] Setup complete!"
echo ""
echo "To start the bot:"
echo "  cd $SCRIPT_DIR"
echo "  source venv/bin/activate"
echo "  python bot.py"
echo ""
echo "Or use the run script:"
echo "  ./run.sh"
echo ""
