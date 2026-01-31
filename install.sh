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

# Configure serial port for RasBee II
# RasBee II requires the PL011 UART (ttyAMA0), not the mini UART
# On Pi 3/4/5, Bluetooth uses PL011 by default - we need to swap them
echo
echo "Configuring serial port for RasBee II..."

REBOOT_NEEDED=false

if [ "$EUID" -eq 0 ] || [ -w /boot/firmware/config.txt ] || [ -w /boot/config.txt ]; then
    # Find the correct config.txt location
    if [ -f /boot/firmware/config.txt ]; then
        CONFIG_FILE="/boot/firmware/config.txt"
    else
        CONFIG_FILE="/boot/config.txt"
    fi

    # Add miniuart-bt overlay if not present (swaps Bluetooth to mini UART)
    if ! grep -q "dtoverlay=miniuart-bt" "$CONFIG_FILE"; then
        echo "Adding dtoverlay=miniuart-bt to $CONFIG_FILE..."
        # Add after [all] section if it exists, otherwise append
        if grep -q "^\[all\]" "$CONFIG_FILE"; then
            sed -i '/^\[all\]/a dtoverlay=miniuart-bt' "$CONFIG_FILE"
        else
            echo "dtoverlay=miniuart-bt" >> "$CONFIG_FILE"
        fi
        REBOOT_NEEDED=true
        echo "  Added miniuart-bt overlay (assigns PL011 UART to GPIO)"
    else
        echo "  miniuart-bt overlay already configured"
    fi

    # Ensure UART is enabled
    if ! grep -q "^enable_uart=1" "$CONFIG_FILE"; then
        echo "enable_uart=1" >> "$CONFIG_FILE"
        REBOOT_NEEDED=true
        echo "  Enabled UART"
    fi

    # Disable serial console on ttyAMA0 (it interferes with RasBee)
    # Check cmdline.txt
    if [ -f /boot/firmware/cmdline.txt ]; then
        CMDLINE_FILE="/boot/firmware/cmdline.txt"
    else
        CMDLINE_FILE="/boot/cmdline.txt"
    fi

    if grep -q "console=serial0" "$CMDLINE_FILE" || grep -q "console=ttyAMA0" "$CMDLINE_FILE"; then
        echo "Removing serial console from $CMDLINE_FILE..."
        sed -i 's/console=serial0,[0-9]* //g' "$CMDLINE_FILE"
        sed -i 's/console=ttyAMA0,[0-9]* //g' "$CMDLINE_FILE"
        REBOOT_NEEDED=true
        echo "  Disabled serial console (was interfering with RasBee)"
    fi

    # Disable serial-getty service
    if systemctl is-enabled serial-getty@ttyAMA0.service &>/dev/null; then
        echo "Disabling serial-getty on ttyAMA0..."
        systemctl stop serial-getty@ttyAMA0.service 2>/dev/null || true
        systemctl disable serial-getty@ttyAMA0.service 2>/dev/null || true
        echo "  Disabled serial-getty service"
    fi

    echo "Serial port configuration complete."
else
    echo "NOTE: Run with sudo to configure serial port:"
    echo "  sudo ./install.sh"
fi

# Setup serial port permissions for RasBee II testing
echo
echo "Setting up serial port permissions..."
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
    chmod 666 /dev/serial0 2>/dev/null || true
    echo "Serial port permissions configured."
else
    echo "NOTE: Run with sudo to configure serial port permissions:"
    echo "  sudo ./install.sh"
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

# Check if reboot is needed for serial port changes
if [ "$REBOOT_NEEDED" = true ]; then
    echo
    echo "****************************************"
    echo "  REBOOT REQUIRED"
    echo "  Serial port configuration changed."
    echo "  Please reboot for RasBee II testing:"
    echo "    sudo reboot"
    echo "****************************************"
fi
