#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================"
echo "  DriveSync Manager — Linux Installer"
echo "  Version 2.1.1"
echo "============================================"
echo

# Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] Python 3 is required but not found."
    echo
    echo "Install it using your package manager:"
    echo "  Ubuntu/Debian:  sudo apt install python3 python3-venv"
    echo "  Fedora:         sudo dnf install python3"
    echo "  Arch:           sudo pacman -S python"
    exit 1
fi

echo "Detected Python: $(python3 --version)"

# Check Tkinter
if ! python3 -c 'import tkinter' >/dev/null 2>&1; then
    echo
    echo "[ERROR] Tkinter is not installed."
    echo
    echo "Install it using your package manager:"
    echo "  Ubuntu/Debian:  sudo apt install python3-tk"
    echo "  Fedora:         sudo dnf install python3-tkinter"
    echo "  Arch:           sudo pacman -S tk"
    echo
    echo "Then run this installer again."
    exit 1
fi

echo "Tkinter: OK"
echo

# Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Upgrade pip and install dependencies
echo "Installing dependencies..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt --quiet

echo
echo "============================================"
echo "  Installation completed successfully!"
echo "============================================"
echo
echo "To start the app, run:"
echo "  ./run_linux.sh"
echo
echo "Or add DriveSyncManager.desktop to your"
echo "application menu for easy access."
