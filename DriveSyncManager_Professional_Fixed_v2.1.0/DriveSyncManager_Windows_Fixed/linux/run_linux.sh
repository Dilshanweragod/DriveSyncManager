#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
    echo "============================================"
    echo "  DriveSync Manager — Not Installed"
    echo "============================================"
    echo
    echo "Please run ./install_linux.sh first."
    exit 1
fi

exec .venv/bin/python DriveSyncManager.py "$@"
