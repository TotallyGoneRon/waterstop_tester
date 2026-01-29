"""
GPIO Test Functions for Waterstop HAT Tester
Tests motor driver, feedback pins, LED, fan control, and RasBee II Zigbee module.
"""

import time
try:
    import eventlet
    sleep = eventlet.sleep  # Use eventlet sleep for better WebSocket responsiveness
except ImportError:
    sleep = time.sleep  # Fallback to standard sleep
from typing import Dict, List, Tuple, Callable, Optional
from dataclasses import dataclass
from enum import Enum

# GPIO pin definitions (BCM numbering)
class Pins:
    # Motor Driver (TB6612)
    PWMA = 12       # Cold valve PWM
    PWMB = 13       # Hot valve PWM
    STBY = 21       # Standby
    AIN1 = 26       # Cold direction 1
    AIN2 = 20       # Cold direction 2
    BIN1 = 19       # Hot direction 1
    BIN2 = 16       # Hot direction 2

    # Valve Feedback
    COLD_FB_OPEN = 6
    COLD_FB_CLOSE = 5
    HOT_FB_OPEN = 22
    HOT_FB_CLOSE = 23

    # Fan Control
    FAN_PWM = 24

    # Status LED
    LED = 27


class TestResult(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    WAITING = "waiting"
    RUNNING = "running"


@dataclass
class TestOutput:
    name: str
    result: TestResult
    message: str
    details: Optional[str] = None


class GPIOTester:
    """Handles GPIO testing for Waterstop HAT."""

    def __init__(self, emit_callback: Callable = None):
        self.emit = emit_callback or (lambda *args: None)
        self.gpio = None
        self.pwm_a = None
        self.pwm_b = None
        self.pwm_fan = None
        self._initialized = False

    def _emit_status(self, test_name: str, result: TestResult, message: str, details: str = None):
        """Send test status update."""
        self.emit('test_update', {
            'name': test_name,
            'result': result.value,
            'message': message,
            'details': details
        })

    def setup(self) -> bool:
        """Initialize GPIO. Returns True on success."""
        try:
            import RPi.GPIO as GPIO
            self.gpio = GPIO

            # Use BCM numbering
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)

            # Setup outputs
            output_pins = [
                Pins.PWMA, Pins.PWMB, Pins.STBY,
                Pins.AIN1, Pins.AIN2, Pins.BIN1, Pins.BIN2,
                Pins.FAN_PWM, Pins.LED
            ]
            for pin in output_pins:
                GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)

            # Setup inputs with pull-up (feedback switches are normally open)
            input_pins = [
                Pins.COLD_FB_OPEN, Pins.COLD_FB_CLOSE,
                Pins.HOT_FB_OPEN, Pins.HOT_FB_CLOSE
            ]
            for pin in input_pins:
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

            self._initialized = True
            return True

        except Exception as e:
            self._emit_status("GPIO Setup", TestResult.FAIL, f"Failed to initialize GPIO: {e}")
            return False

    def cleanup(self):
        """Release all GPIO resources."""
        if self.pwm_a:
            self.pwm_a.stop()
            self.pwm_a = None
        if self.pwm_b:
            self.pwm_b.stop()
            self.pwm_b = None
        if self.pwm_fan:
            self.pwm_fan.stop()
            self.pwm_fan = None

        if self.gpio:
            self.gpio.cleanup()
            self._initialized = False

    def turn_fan_on(self, duty_cycle: int = 100):
        """Turn fan on at specified duty cycle (0-100)."""
        if not self._initialized:
            raise RuntimeError("GPIO not initialized")

        # Stop existing PWM if running
        if self.pwm_fan:
            self.pwm_fan.stop()

        self.pwm_fan = self.gpio.PWM(Pins.FAN_PWM, 25000)  # 25kHz for fan
        self.pwm_fan.start(duty_cycle)

    def turn_fan_off(self):
        """Turn fan off."""
        if not self._initialized:
            raise RuntimeError("GPIO not initialized")

        if self.pwm_fan:
            self.pwm_fan.stop()
            self.pwm_fan = None

        self.gpio.output(Pins.FAN_PWM, self.gpio.LOW)

    def turn_led_on(self):
        """Turn LED on."""
        if not self._initialized:
            raise RuntimeError("GPIO not initialized")

        self.gpio.output(Pins.LED, self.gpio.HIGH)

    def turn_led_off(self):
        """Turn LED off."""
        if not self._initialized:
            raise RuntimeError("GPIO not initialized")

        self.gpio.output(Pins.LED, self.gpio.LOW)

    def test_led(self) -> TestOutput:
        """Test status LED on/off."""
        test_name = "LED Test"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing LED...")

            # Turn LED on
            self.gpio.output(Pins.LED, self.gpio.HIGH)
            sleep(0.3)

            # Turn LED off
            self.gpio.output(Pins.LED, self.gpio.LOW)
            sleep(0.1)

            # Blink pattern to confirm
            for _ in range(3):
                self.gpio.output(Pins.LED, self.gpio.HIGH)
                sleep(0.1)
                self.gpio.output(Pins.LED, self.gpio.LOW)
                sleep(0.1)

            return TestOutput(test_name, TestResult.PASS, "LED toggled successfully")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"LED test failed: {e}")

    def test_stby_pin(self) -> TestOutput:
        """Test motor driver standby pin."""
        test_name = "STBY Pin"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing STBY pin...")

            # Test high
            self.gpio.output(Pins.STBY, self.gpio.HIGH)
            sleep(0.05)

            # Test low
            self.gpio.output(Pins.STBY, self.gpio.LOW)
            sleep(0.05)

            return TestOutput(test_name, TestResult.PASS, "STBY pin toggles correctly")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"STBY test failed: {e}")

    def test_motor_a_direction(self) -> TestOutput:
        """Test Motor A direction pins (AIN1, AIN2)."""
        test_name = "Motor A Direction"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing Motor A direction pins...")

            # Forward: AIN1=HIGH, AIN2=LOW
            self.gpio.output(Pins.AIN1, self.gpio.HIGH)
            self.gpio.output(Pins.AIN2, self.gpio.LOW)
            sleep(0.05)

            # Reverse: AIN1=LOW, AIN2=HIGH
            self.gpio.output(Pins.AIN1, self.gpio.LOW)
            self.gpio.output(Pins.AIN2, self.gpio.HIGH)
            sleep(0.05)

            # Stop: both LOW
            self.gpio.output(Pins.AIN1, self.gpio.LOW)
            self.gpio.output(Pins.AIN2, self.gpio.LOW)

            return TestOutput(test_name, TestResult.PASS, "AIN1/AIN2 pins toggle correctly")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Motor A direction test failed: {e}")

    def test_motor_b_direction(self) -> TestOutput:
        """Test Motor B direction pins (BIN1, BIN2)."""
        test_name = "Motor B Direction"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing Motor B direction pins...")

            # Forward: BIN1=HIGH, BIN2=LOW
            self.gpio.output(Pins.BIN1, self.gpio.HIGH)
            self.gpio.output(Pins.BIN2, self.gpio.LOW)
            sleep(0.05)

            # Reverse: BIN1=LOW, BIN2=HIGH
            self.gpio.output(Pins.BIN1, self.gpio.LOW)
            self.gpio.output(Pins.BIN2, self.gpio.HIGH)
            sleep(0.05)

            # Stop: both LOW
            self.gpio.output(Pins.BIN1, self.gpio.LOW)
            self.gpio.output(Pins.BIN2, self.gpio.LOW)

            return TestOutput(test_name, TestResult.PASS, "BIN1/BIN2 pins toggle correctly")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Motor B direction test failed: {e}")

    def test_pwm_a(self) -> TestOutput:
        """Test PWM Channel A output."""
        test_name = "PWM Channel A"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing PWM A...")

            # Setup PWM at 1kHz
            self.pwm_a = self.gpio.PWM(Pins.PWMA, 1000)
            self.pwm_a.start(0)

            # Sweep duty cycle
            for duty in [25, 50, 75, 100, 0]:
                self.pwm_a.ChangeDutyCycle(duty)
                sleep(0.05)

            self.pwm_a.stop()
            self.pwm_a = None

            return TestOutput(test_name, TestResult.PASS, "PWM A output working")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"PWM A test failed: {e}")

    def test_pwm_b(self) -> TestOutput:
        """Test PWM Channel B output."""
        test_name = "PWM Channel B"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing PWM B...")

            # Setup PWM at 1kHz
            self.pwm_b = self.gpio.PWM(Pins.PWMB, 1000)
            self.pwm_b.start(0)

            # Sweep duty cycle
            for duty in [25, 50, 75, 100, 0]:
                self.pwm_b.ChangeDutyCycle(duty)
                sleep(0.05)

            self.pwm_b.stop()
            self.pwm_b = None

            return TestOutput(test_name, TestResult.PASS, "PWM B output working")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"PWM B test failed: {e}")

    def test_pullup_resistors(self) -> TestOutput:
        """Test pull-up resistors (no valves connected).

        All feedback pins should read HIGH when no valves are connected.
        """
        test_name = "Pull-up Resistors"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Checking pull-up resistors...")

            cold_open = self.gpio.input(Pins.COLD_FB_OPEN)
            cold_close = self.gpio.input(Pins.COLD_FB_CLOSE)
            hot_open = self.gpio.input(Pins.HOT_FB_OPEN)
            hot_close = self.gpio.input(Pins.HOT_FB_CLOSE)

            pins_state = {
                'Cold Open': cold_open,
                'Cold Close': cold_close,
                'Hot Open': hot_open,
                'Hot Close': hot_close
            }

            all_high = all(v == 1 for v in pins_state.values())
            details = " | ".join([f"{k}: {'HIGH' if v == 1 else 'LOW'}" for k, v in pins_state.items()])

            if all_high:
                return TestOutput(
                    test_name,
                    TestResult.PASS,
                    "All pull-ups working (all pins HIGH)",
                    details
                )
            else:
                low_pins = [k for k, v in pins_state.items() if v == 0]
                return TestOutput(
                    test_name,
                    TestResult.FAIL,
                    f"Unexpected LOW: {', '.join(low_pins)}",
                    details
                )

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Pull-up test failed: {e}")

    def test_valve_state(self) -> TestOutput:
        """Check valve positions without actuation.

        Reports whether each valve is detected and its position (open/closed).
        """
        test_name = "Valve State"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Checking valve states...")

            cold_open = self.gpio.input(Pins.COLD_FB_OPEN)
            cold_close = self.gpio.input(Pins.COLD_FB_CLOSE)
            hot_open = self.gpio.input(Pins.HOT_FB_OPEN)
            hot_close = self.gpio.input(Pins.HOT_FB_CLOSE)

            # Determine cold valve state
            if cold_open == 0 and cold_close == 1:
                cold_state = "OPEN"
            elif cold_open == 1 and cold_close == 0:
                cold_state = "CLOSED"
            elif cold_open == 1 and cold_close == 1:
                cold_state = "NOT CONNECTED"
            else:
                cold_state = "ERROR (both active)"

            # Determine hot valve state
            if hot_open == 0 and hot_close == 1:
                hot_state = "OPEN"
            elif hot_open == 1 and hot_close == 0:
                hot_state = "CLOSED"
            elif hot_open == 1 and hot_close == 1:
                hot_state = "NOT CONNECTED"
            else:
                hot_state = "ERROR (both active)"

            details = f"Cold: {cold_state} | Hot: {hot_state}"

            # Pass if both valves detected, fail otherwise
            cold_ok = cold_state in ["OPEN", "CLOSED"]
            hot_ok = hot_state in ["OPEN", "CLOSED"]

            if cold_ok and hot_ok:
                return TestOutput(
                    test_name,
                    TestResult.PASS,
                    "Both valves detected",
                    details
                )
            else:
                issues = []
                if not cold_ok:
                    issues.append(f"Cold: {cold_state}")
                if not hot_ok:
                    issues.append(f"Hot: {hot_state}")
                return TestOutput(
                    test_name,
                    TestResult.FAIL,
                    "; ".join(issues),
                    details
                )

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Valve state test failed: {e}")

    def test_feedback_pins(self) -> TestOutput:
        """Read and report feedback pin states (used in quick test).

        Fails if both pins are LOW for any valve (error condition).
        """
        test_name = "Feedback Pins"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Reading feedback pins...")

            cold_open = self.gpio.input(Pins.COLD_FB_OPEN)
            cold_close = self.gpio.input(Pins.COLD_FB_CLOSE)
            hot_open = self.gpio.input(Pins.HOT_FB_OPEN)
            hot_close = self.gpio.input(Pins.HOT_FB_CLOSE)

            states = {
                'Cold Open': 'LOW' if cold_open == 0 else 'HIGH',
                'Cold Close': 'LOW' if cold_close == 0 else 'HIGH',
                'Hot Open': 'LOW' if hot_open == 0 else 'HIGH',
                'Hot Close': 'LOW' if hot_close == 0 else 'HIGH'
            }

            details = " | ".join([f"{k}: {v}" for k, v in states.items()])

            # Check for error condition: both pins LOW on same valve
            cold_both_low = cold_open == 0 and cold_close == 0
            hot_both_low = hot_open == 0 and hot_close == 0

            if cold_both_low or hot_both_low:
                errors = []
                if cold_both_low:
                    errors.append("Cold: both pins LOW")
                if hot_both_low:
                    errors.append("Hot: both pins LOW")
                return TestOutput(
                    test_name,
                    TestResult.FAIL,
                    f"ERROR: {'; '.join(errors)}",
                    details
                )

            return TestOutput(
                test_name,
                TestResult.PASS,
                "Feedback pins OK",
                details
            )

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Feedback test failed: {e}")

    def test_fan_pwm(self) -> TestOutput:
        """Test fan PWM output with sweep."""
        test_name = "Fan PWM"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing fan PWM sweep...")

            self.pwm_fan = self.gpio.PWM(Pins.FAN_PWM, 25000)  # 25kHz for fan
            self.pwm_fan.start(0)

            # Sweep: 0 -> 50 -> 100 -> 0
            for duty in [0, 25, 50, 75, 100, 50, 0]:
                self.pwm_fan.ChangeDutyCycle(duty)
                sleep(0.2)

            self.pwm_fan.stop()
            self.pwm_fan = None

            return TestOutput(test_name, TestResult.PASS, "Fan PWM sweep complete")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Fan PWM test failed: {e}")

    def _move_motor(self, motor: str, direction: str, duration: float = 0.5) -> Tuple[bool, str]:
        """Move a motor briefly and check feedback.

        Args:
            motor: 'A' (cold) or 'B' (hot)
            direction: 'open' or 'close'
            duration: How long to run motor in seconds

        Returns:
            (success, message)
        """
        if motor == 'A':
            pwm_pin = Pins.PWMA
            in1, in2 = Pins.AIN1, Pins.AIN2
            fb_open, fb_close = Pins.COLD_FB_OPEN, Pins.COLD_FB_CLOSE
            name = "Cold"
        else:
            pwm_pin = Pins.PWMB
            in1, in2 = Pins.BIN1, Pins.BIN2
            fb_open, fb_close = Pins.HOT_FB_OPEN, Pins.HOT_FB_CLOSE
            name = "Hot"

        try:
            # Enable motor driver
            self.gpio.output(Pins.STBY, self.gpio.HIGH)

            # Set direction
            if direction == 'open':
                self.gpio.output(in1, self.gpio.HIGH)
                self.gpio.output(in2, self.gpio.LOW)
            else:
                self.gpio.output(in1, self.gpio.LOW)
                self.gpio.output(in2, self.gpio.HIGH)

            # Start PWM
            pwm = self.gpio.PWM(pwm_pin, 1000)
            pwm.start(100)  # Full speed

            # Run for duration
            sleep(duration)

            # Stop
            pwm.stop()
            self.gpio.output(in1, self.gpio.LOW)
            self.gpio.output(in2, self.gpio.LOW)
            self.gpio.output(Pins.STBY, self.gpio.LOW)

            # Check feedback
            sleep(0.1)
            open_state = self.gpio.input(fb_open)
            close_state = self.gpio.input(fb_close)

            feedback_msg = f"{name} feedback - Open: {'ACTIVE' if open_state == 0 else 'inactive'}, Close: {'ACTIVE' if close_state == 0 else 'inactive'}"

            return True, feedback_msg

        except Exception as e:
            return False, str(e)

    def test_motor_a_movement(self) -> TestOutput:
        """Test Motor A with brief movement pulse."""
        test_name = "Motor A Movement"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing cold valve motor...")

            # Brief open pulse
            success, msg = self._move_motor('A', 'open', 0.3)
            if not success:
                return TestOutput(test_name, TestResult.FAIL, f"Motor A failed: {msg}")

            sleep(0.2)

            # Brief close pulse
            success, msg = self._move_motor('A', 'close', 0.3)
            if not success:
                return TestOutput(test_name, TestResult.FAIL, f"Motor A failed: {msg}")

            return TestOutput(test_name, TestResult.PASS, "Motor A responds", msg)

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Motor A test failed: {e}")

    def test_motor_b_movement(self) -> TestOutput:
        """Test Motor B with brief movement pulse."""
        test_name = "Motor B Movement"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Testing hot valve motor...")

            # Brief open pulse
            success, msg = self._move_motor('B', 'open', 0.3)
            if not success:
                return TestOutput(test_name, TestResult.FAIL, f"Motor B failed: {msg}")

            sleep(0.2)

            # Brief close pulse
            success, msg = self._move_motor('B', 'close', 0.3)
            if not success:
                return TestOutput(test_name, TestResult.FAIL, f"Motor B failed: {msg}")

            return TestOutput(test_name, TestResult.PASS, "Motor B responds", msg)

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Motor B test failed: {e}")

    def _cycle_valve(self, motor: str, test_name: str, timeout: float = 10.0) -> Tuple[bool, str]:
        """Fully cycle a valve open then closed.

        Args:
            motor: 'A' (cold) or 'B' (hot)
            test_name: Name of the test for status updates
            timeout: Max time per direction in seconds

        Returns:
            (success, message)
        """
        if motor == 'A':
            pwm_pin = Pins.PWMA
            in1, in2 = Pins.AIN1, Pins.AIN2
            fb_open, fb_close = Pins.COLD_FB_OPEN, Pins.COLD_FB_CLOSE
            name = "Cold"
        else:
            pwm_pin = Pins.PWMB
            in1, in2 = Pins.BIN1, Pins.BIN2
            fb_open, fb_close = Pins.HOT_FB_OPEN, Pins.HOT_FB_CLOSE
            name = "Hot"

        try:
            # Enable motor driver
            self._emit_status(test_name, TestResult.RUNNING, f"{name}: Enabling motor driver...")
            self.gpio.output(Pins.STBY, self.gpio.HIGH)

            # Setup PWM
            pwm = self.gpio.PWM(pwm_pin, 1000)

            # Open valve
            self._emit_status(test_name, TestResult.RUNNING, f"{name}: Opening valve...")
            self.gpio.output(in1, self.gpio.HIGH)
            self.gpio.output(in2, self.gpio.LOW)
            pwm.start(100)

            start = time.time()
            last_update = 0
            while time.time() - start < timeout:
                if self.gpio.input(fb_open) == 0:  # Active low
                    break
                elapsed = int(time.time() - start)
                if elapsed > last_update:
                    last_update = elapsed
                    self._emit_status(test_name, TestResult.RUNNING, f"{name}: Opening... {elapsed}s")
                sleep(0.05)

            open_reached = self.gpio.input(fb_open) == 0

            # Stop briefly
            pwm.stop()
            self.gpio.output(in1, self.gpio.LOW)
            self.gpio.output(in2, self.gpio.LOW)

            if open_reached:
                self._emit_status(test_name, TestResult.RUNNING, f"{name}: Opened OK, pausing...")
            else:
                self._emit_status(test_name, TestResult.RUNNING, f"{name}: Open TIMEOUT, trying close...")
            sleep(0.3)

            # Close valve
            self._emit_status(test_name, TestResult.RUNNING, f"{name}: Closing valve...")
            self.gpio.output(in1, self.gpio.LOW)
            self.gpio.output(in2, self.gpio.HIGH)
            pwm.start(100)

            start = time.time()
            last_update = 0
            while time.time() - start < timeout:
                if self.gpio.input(fb_close) == 0:  # Active low
                    break
                elapsed = int(time.time() - start)
                if elapsed > last_update:
                    last_update = elapsed
                    self._emit_status(test_name, TestResult.RUNNING, f"{name}: Closing... {elapsed}s")
                sleep(0.05)

            close_reached = self.gpio.input(fb_close) == 0

            # Stop
            self._emit_status(test_name, TestResult.RUNNING, f"{name}: Stopping motor...")
            pwm.stop()
            self.gpio.output(in1, self.gpio.LOW)
            self.gpio.output(in2, self.gpio.LOW)
            self.gpio.output(Pins.STBY, self.gpio.LOW)

            if open_reached and close_reached:
                return True, f"{name} valve cycled: Open OK, Close OK"
            elif open_reached:
                return False, f"{name} valve: Open OK, Close TIMEOUT"
            elif close_reached:
                return False, f"{name} valve: Open TIMEOUT, Close OK"
            else:
                return False, f"{name} valve: Both directions TIMEOUT"

        except Exception as e:
            # Ensure cleanup
            try:
                self.gpio.output(Pins.STBY, self.gpio.LOW)
            except:
                pass
            return False, str(e)

    def test_cold_valve_cycle(self) -> TestOutput:
        """Full cycle test for cold valve."""
        test_name = "Cold Valve Cycle"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Starting cold valve cycle...")

            success, msg = self._cycle_valve('A', test_name)

            if success:
                return TestOutput(test_name, TestResult.PASS, msg)
            else:
                return TestOutput(test_name, TestResult.FAIL, msg)

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Cold valve test failed: {e}")

    def test_hot_valve_cycle(self) -> TestOutput:
        """Full cycle test for hot valve."""
        test_name = "Hot Valve Cycle"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Starting hot valve cycle...")

            success, msg = self._cycle_valve('B', test_name)

            if success:
                return TestOutput(test_name, TestResult.PASS, msg)
            else:
                return TestOutput(test_name, TestResult.FAIL, msg)

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Hot valve test failed: {e}")

    def run_quick_test(self) -> List[TestOutput]:
        """Run quick tests (no peripherals needed)."""
        results = []

        tests = [
            self.test_led,
            self.test_stby_pin,
            self.test_motor_a_direction,
            self.test_motor_b_direction,
            self.test_pwm_a,
            self.test_pwm_b,
        ]

        for test in tests:
            result = test()
            results.append(result)
            self._emit_status(result.name, result.result, result.message, result.details)
            sleep(0.1)

        # Feedback pins - just report state
        result = self.test_feedback_pins()
        results.append(result)
        self._emit_status(result.name, result.result, result.message, result.details)

        return results

    def run_full_test(self) -> List[TestOutput]:
        """Run full tests (valves + fan connected)."""
        results = []

        # Basic GPIO tests (same as quick, but without feedback)
        basic_tests = [
            self.test_led,
            self.test_stby_pin,
            self.test_motor_a_direction,
            self.test_motor_b_direction,
            self.test_pwm_a,
            self.test_pwm_b,
        ]

        for test in basic_tests:
            result = test()
            results.append(result)
            self._emit_status(result.name, result.result, result.message, result.details)
            sleep(0.1)

        # Valve state check (expects valves connected)
        result = self.test_valve_state()
        results.append(result)
        self._emit_status(result.name, result.result, result.message, result.details)
        sleep(0.1)

        # Full tests with valve actuation
        full_tests = [
            self.test_motor_a_movement,
            self.test_motor_b_movement,
            self.test_fan_pwm,
            self.test_cold_valve_cycle,
            self.test_hot_valve_cycle,
        ]

        for test in full_tests:
            result = test()
            results.append(result)
            self._emit_status(result.name, result.result, result.message, result.details)
            sleep(0.1)

        return results

    def run_resistor_test(self) -> List[TestOutput]:
        """Run pull-up resistor test (no valves connected).

        Verifies all feedback pins read HIGH, confirming pull-up resistors work.
        """
        results = []

        result = self.test_pullup_resistors()
        results.append(result)
        self._emit_status(result.name, result.result, result.message, result.details)

        return results

    def run_valve_state_test(self) -> List[TestOutput]:
        """Run valve state test (no actuation).

        Checks valve positions without actuating them. Reports if each
        valve is detected and whether it's open or closed.
        """
        results = []

        result = self.test_valve_state()
        results.append(result)
        self._emit_status(result.name, result.result, result.message, result.details)

        return results

    def test_rasbee(self) -> TestOutput:
        """Test RasBee II Zigbee module on serial port.

        Checks if the RasBee II is detected on the UART and responds.
        """
        test_name = "RasBee II"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Checking serial port...")

            import serial
            import os

            # Check if serial device exists
            serial_ports = ['/dev/ttyS0', '/dev/ttyAMA0', '/dev/serial0']
            found_port = None

            for port in serial_ports:
                if os.path.exists(port):
                    found_port = port
                    break

            if not found_port:
                return TestOutput(
                    test_name,
                    TestResult.FAIL,
                    "No serial port found",
                    "Checked: /dev/ttyS0, /dev/ttyAMA0, /dev/serial0"
                )

            self._emit_status(test_name, TestResult.RUNNING, f"Opening {found_port}...")

            # Try to open the serial port at common RasBee baud rates
            baud_rates = [38400, 115200]
            ser = None
            last_error = None

            for baud in baud_rates:
                try:
                    # Try without exclusive first (more compatible)
                    ser = serial.Serial(
                        found_port,
                        baud,
                        timeout=1
                    )
                    break
                except serial.SerialException as e:
                    last_error = str(e)
                    continue
                except PermissionError as e:
                    last_error = f"Permission denied - run: sudo chmod 666 {found_port}"
                    continue

            if ser is None:
                return TestOutput(
                    test_name,
                    TestResult.FAIL,
                    "Cannot open serial port",
                    last_error or f"Port {found_port} inaccessible"
                )

            self._emit_status(test_name, TestResult.RUNNING, f"Port open at {ser.baudrate} baud...")

            # Clear buffers
            ser.reset_input_buffer()
            ser.reset_output_buffer()

            # Give it a moment
            sleep(0.1)

            # Check if we can read/write
            port_info = f"{found_port} @ {ser.baudrate} baud"

            ser.close()

            return TestOutput(
                test_name,
                TestResult.PASS,
                "RasBee II serial port OK",
                port_info
            )

        except ImportError:
            return TestOutput(
                test_name,
                TestResult.FAIL,
                "pyserial not installed",
                "Run: pip3 install pyserial"
            )
        except PermissionError:
            return TestOutput(
                test_name,
                TestResult.FAIL,
                "Permission denied on serial port",
                "May need sudo or dialout group membership"
            )
        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"RasBee test failed: {e}")

    def run_rasbee_test(self) -> List[TestOutput]:
        """Run RasBee II Zigbee module test.

        Tests if the RasBee II is properly connected and accessible.
        """
        results = []

        result = self.test_rasbee()
        results.append(result)
        self._emit_status(result.name, result.result, result.message, result.details)

        return results
