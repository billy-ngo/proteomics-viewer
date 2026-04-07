#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================"
echo "  Pro-ker Proteomics Viewer Installer"
echo "============================================"
echo

# Check for Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Install via: brew install python3"
    echo "Or download from https://python.org"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Installing Pro-ker Proteomics Viewer..."
pip3 install -e "$SCRIPT_DIR" --quiet

echo
echo "Installation complete!"
echo
echo "Usage:"
echo "  proker                    Start the viewer"
echo "  proker file.txt           Start with a file pre-loaded"
echo "  proker --port 9000        Use a custom port"
echo
echo "Starting Pro-ker Proteomics Viewer now..."
echo
proker
