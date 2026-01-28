# Waterstop HAT Tester

Web-based testing tool for quality control of custom Waterstop HATs during assembly.

## Features

- **Web-based interface** - Access from any browser on your network (phone, tablet, laptop)
- **Real-time updates** - See test progress live via WebSocket
- **Two test modes**:
  - **Quick Test** - GPIO-only tests, no peripherals needed
  - **Full Test** - Complete tests including valve cycles and fan control
- **No reboot required** - Swap HATs and test again immediately
- **Test history** - Last 10 tests displayed for tracking

## Quick Start

### On Raspberry Pi

```bash
# Clone the repository
cd ~
git clone https://github.com/TotallyGoneRon/waterstop_tester.git
cd waterstop_tester

# Install dependencies
./install.sh
# OR
pip3 install -r requirements.txt

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
7. Feedback pin reading (reports state)

### Full Test (valves + fan connected)
All quick tests plus:
8. Motor A movement (brief pulse, check feedback)
9. Motor B movement (brief pulse, check feedback)
10. Fan PWM sweep (0% → 50% → 100%)
11. Cold valve cycle (open → close)
12. Hot valve cycle (open → close)

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
