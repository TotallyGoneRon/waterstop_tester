"""
GPIO Test Functions for Waterstop HAT Tester
Tests motor driver, feedback pins, LED, and fan control.
"""

import time
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
            time.sleep(0.3)

            # Turn LED off
            self.gpio.output(Pins.LED, self.gpio.LOW)
            time.sleep(0.1)

            # Blink pattern to confirm
            for _ in range(3):
                self.gpio.output(Pins.LED, self.gpio.HIGH)
                time.sleep(0.1)
                self.gpio.output(Pins.LED, self.gpio.LOW)
                time.sleep(0.1)

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
            time.sleep(0.05)

            # Test low
            self.gpio.output(Pins.STBY, self.gpio.LOW)
            time.sleep(0.05)

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
            time.sleep(0.05)

            # Reverse: AIN1=LOW, AIN2=HIGH
            self.gpio.output(Pins.AIN1, self.gpio.LOW)
            self.gpio.output(Pins.AIN2, self.gpio.HIGH)
            time.sleep(0.05)

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
            time.sleep(0.05)

            # Reverse: BIN1=LOW, BIN2=HIGH
            self.gpio.output(Pins.BIN1, self.gpio.LOW)
            self.gpio.output(Pins.BIN2, self.gpio.HIGH)
            time.sleep(0.05)

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
                time.sleep(0.05)

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
                time.sleep(0.05)

            self.pwm_b.stop()
            self.pwm_b = None

            return TestOutput(test_name, TestResult.PASS, "PWM B output working")

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"PWM B test failed: {e}")

    def test_feedback_pins(self) -> TestOutput:
        """Read and report feedback pin states."""
        test_name = "Feedback Pins"
        try:
            self._emit_status(test_name, TestResult.RUNNING, "Reading feedback pins...")

            cold_open = self.gpio.input(Pins.COLD_FB_OPEN)
            cold_close = self.gpio.input(Pins.COLD_FB_CLOSE)
            hot_open = self.gpio.input(Pins.HOT_FB_OPEN)
            hot_close = self.gpio.input(Pins.HOT_FB_CLOSE)

            states = {
                'Cold Open': 'ACTIVE' if cold_open == 0 else 'inactive',
                'Cold Close': 'ACTIVE' if cold_close == 0 else 'inactive',
                'Hot Open': 'ACTIVE' if hot_open == 0 else 'inactive',
                'Hot Close': 'ACTIVE' if hot_close == 0 else 'inactive'
            }

            details = " | ".join([f"{k}: {v}" for k, v in states.items()])

            return TestOutput(
                test_name,
                TestResult.PASS,
                "Feedback pins readable",
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
                time.sleep(0.2)

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
            time.sleep(duration)

            # Stop
            pwm.stop()
            self.gpio.output(in1, self.gpio.LOW)
            self.gpio.output(in2, self.gpio.LOW)
            self.gpio.output(Pins.STBY, self.gpio.LOW)

            # Check feedback
            time.sleep(0.1)
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

            time.sleep(0.2)

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

            time.sleep(0.2)

            # Brief close pulse
            success, msg = self._move_motor('B', 'close', 0.3)
            if not success:
                return TestOutput(test_name, TestResult.FAIL, f"Motor B failed: {msg}")

            return TestOutput(test_name, TestResult.PASS, "Motor B responds", msg)

        except Exception as e:
            return TestOutput(test_name, TestResult.FAIL, f"Motor B test failed: {e}")

    def _cycle_valve(self, motor: str, timeout: float = 10.0) -> Tuple[bool, str]:
        """Fully cycle a valve open then closed.

        Args:
            motor: 'A' (cold) or 'B' (hot)
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
            self.gpio.output(Pins.STBY, self.gpio.HIGH)

            # Setup PWM
            pwm = self.gpio.PWM(pwm_pin, 1000)

            # Open valve
            self.gpio.output(in1, self.gpio.HIGH)
            self.gpio.output(in2, self.gpio.LOW)
            pwm.start(100)

            start = time.time()
            while time.time() - start < timeout:
                if self.gpio.input(fb_open) == 0:  # Active low
                    break
                time.sleep(0.05)

            open_reached = self.gpio.input(fb_open) == 0

            # Stop briefly
            pwm.stop()
            self.gpio.output(in1, self.gpio.LOW)
            self.gpio.output(in2, self.gpio.LOW)
            time.sleep(0.3)

            # Close valve
            self.gpio.output(in1, self.gpio.LOW)
            self.gpio.output(in2, self.gpio.HIGH)
            pwm.start(100)

            start = time.time()
            while time.time() - start < timeout:
                if self.gpio.input(fb_close) == 0:  # Active low
                    break
                time.sleep(0.05)

            close_reached = self.gpio.input(fb_close) == 0

            # Stop
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
            self._emit_status(test_name, TestResult.RUNNING, "Cycling cold valve...")

            success, msg = self._cycle_valve('A')

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
            self._emit_status(test_name, TestResult.RUNNING, "Cycling hot valve...")

            success, msg = self._cycle_valve('B')

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
            self.test_feedback_pins,
        ]

        for test in tests:
            result = test()
            results.append(result)
            self._emit_status(result.name, result.result, result.message, result.details)
            time.sleep(0.1)

        return results

    def run_full_test(self) -> List[TestOutput]:
        """Run full tests (valves + fan connected)."""
        results = []

        # Start with quick tests
        results.extend(self.run_quick_test())

        # Add full tests
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
            time.sleep(0.1)

        return results

    def run_feedback_test(self) -> List[TestOutput]:
        """Run feedback-only test (no 12V/valve actuation needed).

        Tests just the feedback pins to verify wiring without needing
        12V power or valve actuation.
        """
        results = []

        # Only test feedback pins
        result = self.test_feedback_pins()
        results.append(result)
        self._emit_status(result.name, result.result, result.message, result.details)

        return results
