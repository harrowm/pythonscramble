#!/usr/bin/env bash
set -e

if ! command -v uv &>/dev/null; then
    echo "Installing uv via Homebrew..."
    brew install uv
fi

uv sync --no-install-project

echo ""
echo "Done! Run the game with:  uv run python main.py"
