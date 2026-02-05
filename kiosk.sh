#!/bin/bash
# Waterstop HAT Tester - Kiosk Mode Launcher
# Called from LabWC autostart to run Chromium in kiosk mode

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Wait for the waterstop-tester web service to be ready (max 30s)
echo "Kiosk: Waiting for Waterstop Tester service..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8200 > /dev/null 2>&1; then
        echo "Kiosk: Service is ready."
        break
    fi
    sleep 1
done

# Small delay to ensure page is fully loaded
sleep 1

# Launch Chromium in kiosk mode
# --ozone-platform=wayland is required for LabWC (Wayland compositor)
exec chromium \
    --ozone-platform=wayland \
    --kiosk \
    --noerrdialogs \
    --disable-infobars \
    --no-first-run \
    --disable-translate \
    --disable-features=TranslateUI,IdleDetection \
    --check-for-update-interval=31536000 \
    --disable-pinch \
    --overscroll-history-navigation=disabled \
    --disable-session-crashed-bubble \
    --disable-component-update \
    --autoplay-policy=no-user-gesture-required \
    http://localhost:8200
