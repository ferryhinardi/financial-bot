#!/bin/bash
# ──────────────────────────────────────────────────
# Financial Tracker Bot - Run Script
# ──────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "Run setup.sh first: ./setup.sh"
    exit 1
fi

source venv/bin/activate

if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and configure it."
    exit 1
fi

echo "Starting Financial Tracker Bot..."
python bot.py
