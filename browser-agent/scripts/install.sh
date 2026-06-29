#!/usr/bin/env bash
set -e

echo "=== Browser Agent Installer ==="
echo ""

# Check Python
echo "[1/4] Checking Python..."
if command -v python3 &>/dev/null; then
    echo "  Python: $(python3 --version)"
else
    echo "  ERROR: Python 3 not found"
    exit 1
fi

# Install Python deps
echo "[2/4] Installing Python dependencies..."
pip3 install playwright --quiet 2>/dev/null
python3 -m playwright install chromium 2>&1 | tail -1

# Check Node.js
echo "[3/4] Checking Node.js..."
if command -v node &>/dev/null; then
    echo "  Node: $(node --version)"
else
    echo "  WARNING: Node.js not found (optional for agent-browser CLI)"
fi

# Install agent-browser CLI
if command -v npm &>/dev/null; then
    echo "[4/4] Installing agent-browser CLI (Vercel)..."
    npm install -g agent-browser 2>/dev/null
    agent-browser install 2>/dev/null || true
fi

echo ""
echo "=== Install Complete ==="
echo ""
echo "Run: python3 scripts/browser_agent.py --help"
