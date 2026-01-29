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

# Setup serial port permissions for RasBee II testing
echo
echo "Setting up serial port permissions for RasBee II..."
UDEV_RULE='KERNEL=="ttyS0", MODE="0666"'
UDEV_RULE_AMA='KERNEL=="ttyAMA0", MODE="0666"'
UDEV_FILE="/etc/udev/rules.d/99-waterstop-serial.rules"

if [ -w /etc/udev/rules.d ] || [ "$EUID" -eq 0 ]; then
    echo "$UDEV_RULE" > "$UDEV_FILE"
    echo "$UDEV_RULE_AMA" >> "$UDEV_FILE"
    echo "Created udev rule: $UDEV_FILE"

    # Reload udev rules
    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true

    # Also set permissions immediately
    chmod 666 /dev/ttyS0 2>/dev/null || true
    chmod 666 /dev/ttyAMA0 2>/dev/null || true
    echo "Serial port permissions configured."
else
    echo "NOTE: Run with sudo to configure serial port permissions:"
    echo "  sudo ./install.sh"
    echo
    echo "Or manually create the udev rule:"
    echo "  echo '$UDEV_RULE' | sudo tee $UDEV_FILE"
    echo "  sudo udevadm control --reload-rules"
fi

# Install systemd service for auto-start and persistence
echo
echo "Installing systemd service..."
SERVICE_FILE="/etc/systemd/system/waterstop-tester.service"

if [ -w /etc/systemd/system ] || [ "$EUID" -eq 0 ]; then
    # Update paths in service file to match install location
    sed "s|/home/waterstoppro/waterstop_tester|$SCRIPT_DIR|g" "$SCRIPT_DIR/waterstop-tester.service" > "$SERVICE_FILE"

    systemctl daemon-reload
    systemctl enable waterstop-tester
    systemctl start waterstop-tester

    echo "Service installed and started!"
    echo "The tester will now run on boot and survive terminal closure."
else
    echo "NOTE: Run with sudo to install the systemd service:"
    echo "  sudo ./install.sh"
fi

echo
echo "Installation complete!"
echo
echo "========================================"
echo "  SERVICE COMMANDS:"
echo "  sudo systemctl start waterstop-tester"
echo "  sudo systemctl stop waterstop-tester"
echo "  sudo systemctl status waterstop-tester"
echo "  sudo journalctl -u waterstop-tester -f"
echo ""
echo "  Or run manually:"
echo "  python3 $SCRIPT_DIR/app.py"
echo ""
echo "  Open in browser:"
echo "  http://<pi-ip>:8200"
echo "========================================"
