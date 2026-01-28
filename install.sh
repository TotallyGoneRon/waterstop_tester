#!/bin/bash
# Waterstop HAT Tester - Installation Script
# Run this on the Raspberry Pi to set up the tester

set -e

echo "========================================"
echo "  WATERSTOP HAT TESTER - INSTALLER"
echo "========================================"
echo

# Check if running on Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "WARNING: This doesn't appear to be a Raspberry Pi."
    echo "GPIO tests will not work on this machine."
    echo
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Installing Python dependencies..."
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

echo
echo "Installation complete!"
echo
echo "========================================"
echo "  TO RUN THE TESTER:"
echo "  python3 $SCRIPT_DIR/app.py"
echo ""
echo "  Then open in browser:"
echo "  http://<pi-ip>:8200"
echo "========================================"
