#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Chess Rocket — One-Command Launcher
# ==============================================================================
#
# QUICK START:
#   ./scripts/play.sh          # Start on default port 8088
#   ./scripts/play.sh 3000     # Start on custom port
#
# FEATURES:
#   ✓ Auto-checks and installs uv (Python package manager)
#   ✓ Auto-checks and installs Stockfish (chess engine)
#   ✓ Installs Python dependencies (python-chess, rich, textual, etc.)
#   ✓ Creates required data directories
#   ✓ Opens browser automatically (background, doesn't block)
#   ✓ Runs dashboard server on http://localhost:8088
#
# REQUIREMENTS:
#   - Python 3.10+ (checked by uv)
#   - curl or wget (for uv installation)
#   - apt-get (Debian/Ubuntu) or brew (macOS) for Stockfish auto-install
#
# MANUAL INSTALLATION:
#   If auto-install fails, install manually:
#   - uv:      https://docs.astral.sh/uv/getting-started/installation/
#   - Stockfish: https://stockfishchess.org/download/
#
# TROUBLESHOOTING:
#   - "stockfish: command not found" → Install Stockfish manually
#   - "uv: command not found" → Run: curl -LsSf https://astral.sh/uv/install.sh | sh
#   - Port already in use → Run with custom port: ./scripts/play.sh 3000
#
# ==============================================================================

cd "$(dirname "$0")/.."

PORT="${1:-8088}"

# Check uv
if ! command -v uv &>/dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Check stockfish
if ! command -v stockfish &>/dev/null; then
    echo "Stockfish not found. Installing..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get install -y stockfish
    elif command -v brew &>/dev/null; then
        brew install stockfish
    else
        echo "ERROR: Install stockfish manually: https://stockfishchess.org/download/"
        exit 1
    fi
fi

# Install Python deps
echo "Installing dependencies..."
uv sync --quiet 2>/dev/null || uv pip install chess 2>/dev/null

# Ensure data dirs exist
mkdir -p data/games data/sessions data/lesson_plans

echo "Starting Chess Rocket on http://localhost:$PORT"
echo "Press Ctrl+C to stop"

# Open browser (background, don't block)
sleep 1
if command -v xdg-open &>/dev/null; then
    xdg-open "http://localhost:$PORT" 2>/dev/null &
elif command -v open &>/dev/null; then
    open "http://localhost:$PORT" 2>/dev/null &
fi

exec uv run python scripts/dashboard_server.py --port "$PORT"
