#!/bin/bash
# Waterstop HAT Tester - Installation Script
# Run this on the Raspberry Pi to set up the tester
# Usage: sudo ./install.sh

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

# Determine the actual user (not root when running with sudo)
if [ -n "$SUDO_USER" ]; then
    REAL_USER="$SUDO_USER"
    REAL_HOME=$(eval echo ~"$SUDO_USER")
else
    REAL_USER="$(whoami)"
    REAL_HOME="$HOME"
fi

echo "Installing for user: $REAL_USER"
echo "Home directory: $REAL_HOME"
echo "Script directory: $SCRIPT_DIR"
echo

REBOOT_NEEDED=false

# ----------------------------------------
# 1. Python Dependencies
# ----------------------------------------
echo "Installing Python dependencies..."
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

# ----------------------------------------
# 2. Download Socket.IO client for offline use
# ----------------------------------------
echo
echo "Setting up Socket.IO client for offline use..."
SOCKETIO_JS="$SCRIPT_DIR/static/socket.io.min.js"
if [ ! -f "$SOCKETIO_JS" ]; then
    if curl -sL "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.5.4/socket.io.min.js" -o "$SOCKETIO_JS" 2>/dev/null; then
        echo "Downloaded socket.io.min.js for offline use."
    else
        echo "WARNING: Could not download socket.io.min.js - will need internet for first use."
    fi
    chown "$REAL_USER:$REAL_USER" "$SOCKETIO_JS" 2>/dev/null || true
else
    echo "Socket.IO client already present."
fi

# ----------------------------------------
# 3. Serial Port Configuration (RasBee II)
# ----------------------------------------
# RasBee II requires the PL011 UART (ttyAMA0), not the mini UART
# On Pi 3/4/5, Bluetooth uses PL011 by default - we need to swap them
echo
echo "Configuring serial port for RasBee II..."

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

# ----------------------------------------
# 4. Serial Port Permissions
# ----------------------------------------
echo
echo "Setting up serial port permissions..."
UDEV_RULE='KERNEL=="ttyS0", MODE="0666"'
UDEV_RULE_AMA='KERNEL=="ttyAMA0", MODE="0666"'
UDEV_FILE="/etc/udev/rules.d/99-waterstop-serial.rules"

if [ -w /etc/udev/rules.d ] || [ "$EUID" -eq 0 ]; then
    echo "$UDEV_RULE" > "$UDEV_FILE"
    echo "$UDEV_RULE_AMA" >> "$UDEV_FILE"
    echo "Created udev rule: $UDEV_FILE"

    udevadm control --reload-rules 2>/dev/null || true
    udevadm trigger 2>/dev/null || true

    chmod 666 /dev/ttyS0 2>/dev/null || true
    chmod 666 /dev/ttyAMA0 2>/dev/null || true
    chmod 666 /dev/serial0 2>/dev/null || true
    echo "Serial port permissions configured."
else
    echo "NOTE: Run with sudo to configure serial port permissions:"
    echo "  sudo ./install.sh"
fi

# ----------------------------------------
# 5. Systemd Service (Web Server)
# ----------------------------------------
echo
echo "Installing systemd service..."
SERVICE_FILE="/etc/systemd/system/waterstop-tester.service"

if [ -w /etc/systemd/system ] || [ "$EUID" -eq 0 ]; then
    sed "s|/home/waterstoppro/waterstop_tester|$SCRIPT_DIR|g" "$SCRIPT_DIR/waterstop-tester.service" > "$SERVICE_FILE"

    systemctl daemon-reload
    systemctl enable waterstop-tester
    systemctl restart waterstop-tester

    echo "Service installed and started!"
else
    echo "NOTE: Run with sudo to install the systemd service."
fi

# ----------------------------------------
# 6. Kiosk Mode Setup
# ----------------------------------------
echo
echo "Setting up kiosk mode..."

# Make kiosk launcher executable
chmod +x "$SCRIPT_DIR/kiosk.sh"

# Create LabWC autostart directory
LABWC_DIR="$REAL_HOME/.config/labwc"
mkdir -p "$LABWC_DIR"

# Back up existing autostart if present
if [ -f "$LABWC_DIR/autostart" ]; then
    cp "$LABWC_DIR/autostart" "$LABWC_DIR/autostart.bak"
    echo "Backed up existing autostart to autostart.bak"
fi

# Create LabWC autostart for kiosk mode
cat > "$LABWC_DIR/autostart" << AUTOSTART
# Waterstop HAT Tester - Kiosk Mode
# This replaces the default desktop with the test interface
# To restore normal desktop, delete this file and reboot

# Launch the kiosk browser
$SCRIPT_DIR/kiosk.sh &
AUTOSTART

chown -R "$REAL_USER:$REAL_USER" "$LABWC_DIR"
echo "LabWC kiosk autostart created."

# Ensure LightDM autologin is configured
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
if [ -f "$LIGHTDM_CONF" ]; then
    if ! grep -q "autologin-user=$REAL_USER" "$LIGHTDM_CONF"; then
        if grep -q "^\[Seat:\*\]" "$LIGHTDM_CONF"; then
            if grep -q "^autologin-user=" "$LIGHTDM_CONF"; then
                sed -i "s/^autologin-user=.*/autologin-user=$REAL_USER/" "$LIGHTDM_CONF"
            elif grep -q "^#autologin-user=" "$LIGHTDM_CONF"; then
                sed -i "s/^#autologin-user=.*/autologin-user=$REAL_USER/" "$LIGHTDM_CONF"
            else
                sed -i "/^\[Seat:\*\]/a autologin-user=$REAL_USER" "$LIGHTDM_CONF"
            fi
        fi
        echo "LightDM autologin configured for $REAL_USER."
    else
        echo "LightDM autologin already configured."
    fi
fi

# Ensure graphical boot target
systemctl set-default graphical.target 2>/dev/null || true

# Disable screen blanking via LabWC environment
cat > "$LABWC_DIR/environment" << 'ENVFILE'
# Disable screen blanking for kiosk mode
XDG_SESSION_TYPE=wayland
ENVFILE
chown "$REAL_USER:$REAL_USER" "$LABWC_DIR/environment"

echo
echo "========================================"
echo "  INSTALLATION COMPLETE!"
echo "========================================"
echo
echo "  Kiosk mode is now configured."
echo "  On next boot, Chromium will automatically"
echo "  open the Waterstop HAT Tester interface."
echo
echo "  SERVICE COMMANDS:"
echo "  sudo systemctl start waterstop-tester"
echo "  sudo systemctl stop waterstop-tester"
echo "  sudo systemctl status waterstop-tester"
echo "  sudo journalctl -u waterstop-tester -f"
echo
echo "  TO DISABLE KIOSK MODE:"
echo "  rm $LABWC_DIR/autostart"
echo "  (then reboot for normal desktop)"
echo
echo "  TO RESTORE KIOSK MODE:"
echo "  sudo ./install.sh"
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
