#!/usr/bin/env bash
# Launch the Fitbit Dashboard as a standalone desktop application
cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null
python fitbit_desktop.py
