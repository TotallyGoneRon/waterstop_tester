# Waterstop HAT Tester

Web-based testing tool for quality control of custom Waterstop HATs during assembly.

## Features

- **Web-based interface** - Access from any browser on your network (phone, tablet, laptop)
- **Real-time updates** - See test progress live via WebSocket
- **Multiple test modes**:
  - **Quick Test** - GPIO-only tests, no peripherals needed
  - **Full Test** - Complete tests including valve cycles and fan control
  - **Resistor Test** - Verify pull-up resistors (no valves connected)
  - **Valve State** - Check valve positions without actuation
  - **RasBee II** - Test Zigbee module serial connectivity
- **Manual controls** - Toggle FAN and LED for visual verification
- **No reboot required** - Swap HATs and test again immediately
- **Test history** - Last 10 tests displayed for tracking

## Quick Start

### On Raspberry Pi

```bash
# Clone the repository
cd ~
git clone https://github.com/TotallyGoneRon/waterstop_tester.git
cd waterstop_tester

# Install dependencies and configure serial port (run with sudo for RasBee II support)
sudo ./install.sh

# Run the tester
python3 app.py
```

### Access the Web UI

Open in any browser:
```
http://<pi-ip>:8200
```

## GPIO Pin Mapping

| Function | BCM Pin | Physical Pin | Direction |
|----------|---------|--------------|-----------|
| **Motor Driver (TB6612)** |
| PWMA (Cold valve) | 12 | 32 | Output (PWM) |
| PWMB (Hot valve) | 13 | 33 | Output (PWM) |
| STBY (Standby) | 21 | 40 | Output |
| AIN1 (Cold dir 1) | 26 | 37 | Output |
| AIN2 (Cold dir 2) | 20 | 38 | Output |
| BIN1 (Hot dir 1) | 19 | 35 | Output |
| BIN2 (Hot dir 2) | 16 | 36 | Output |
| **Valve Feedback** |
| Cold FB Open | 6 | 31 | Input |
| Cold FB Close | 5 | 29 | Input |
| Hot FB Open | 22 | 15 | Input |
| Hot FB Close | 23 | 16 | Input |
| **Fan Control** |
| FAN PWM | 24 | 18 | Output (PWM) |
| **Status LED** |
| LED | 27 | 13 | Output |

## Test Categories

### Quick Test (no peripherals needed)
1. LED on/off toggle
2. STBY pin high/low
3. Motor A direction pins (AIN1, AIN2)
4. Motor B direction pins (BIN1, BIN2)
5. PWM A output test
6. PWM B output test
7. Feedback pin reading (reports state, fails if both pins LOW)

### Full Test (valves + fan connected)
All quick tests plus:
8. Valve State check (verifies both valves detected)
9. Motor A movement (brief pulse, check feedback)
10. Motor B movement (brief pulse, check feedback)
11. Fan PWM sweep (0% → 50% → 100%)
12. Cold valve cycle (open → close with feedback verification)
13. Hot valve cycle (open → close with feedback verification)

### Resistor Test (no valves)
- Verifies all 4 feedback pull-up resistors
- All pins must read HIGH when no valves connected
- Fails if any pin is unexpectedly LOW (short to ground)

### Valve State (no actuation)
- Checks valve positions without 12V/actuation
- Reports each valve as: OPEN, CLOSED, NOT CONNECTED, or ERROR
- Useful for verifying valve wiring before full test

### RasBee II (Zigbee module)
- Tests serial port connectivity to RasBee II module
- Checks /dev/ttyS0 or /dev/ttyAMA0 at 38400/115200 baud
- Verifies the Zigbee coordinator is accessible

## Updating

```bash
cd ~/waterstop_tester
git pull
```

## Troubleshooting

### "GPIO library not available"
- Make sure you're running on a Raspberry Pi
- Install RPi.GPIO: `pip3 install RPi.GPIO`

### Permission denied on GPIO
- Run with sudo: `sudo python3 app.py`
- Or add user to gpio group: `sudo usermod -aG gpio $USER`

### Port 8200 in use
- Check what's using it: `sudo lsof -i :8200`
- Change port in app.py if needed

### RasBee II test fails with "Permission denied"
The serial port needs read/write permissions. Run install.sh with sudo:
```bash
sudo ./install.sh
```

Or manually fix permissions:
```bash
# Temporary fix (resets on reboot)
sudo chmod 666 /dev/ttyS0

# Permanent fix (udev rule)
echo 'KERNEL=="ttyS0", MODE="0666"' | sudo tee /etc/udev/rules.d/99-waterstop-serial.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### RasBee II test fails with "Port in use"
Another process may be using the serial port:
```bash
# Check what's using the port
sudo lsof /dev/ttyS0

# Common culprits: zigbee2mqtt, deconz, serial-getty
sudo systemctl stop zigbee2mqtt
sudo systemctl stop serial-getty@ttyS0
```

## File Structure

```
waterstop_tester/
├── README.md           # This file
├── requirements.txt    # Python dependencies
├── app.py              # Flask web app (main entry point)
├── gpio_tests.py       # GPIO test functions
├── templates/
│   └── index.html      # Web UI template
├── static/
│   └── style.css       # Styling
└── install.sh          # Easy install script
```

## License

Internal tool for Waterstop HAT QC.
