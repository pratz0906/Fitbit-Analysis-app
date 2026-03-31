#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

echo "============================================"
echo "  Fitbit Dashboard - Starting..."
echo "============================================"
echo

# Check Python is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is not installed."
    echo "Please install Python 3.10+ first."
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo
fi

# Activate virtual environment
source .venv/bin/activate

# Install / upgrade dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet
echo

# Open browser (works on macOS and Linux)
echo "Opening browser..."
if command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5000 &
elif command -v open &> /dev/null; then
    open http://localhost:5000 &
fi

# Start the Flask app
echo
echo "============================================"
echo "  Dashboard running at http://localhost:5000"
echo "  Press Ctrl+C to stop the server."
echo "============================================"
echo
python app.py
