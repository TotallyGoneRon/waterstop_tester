#!/usr/bin/env python3
"""
Waterstop HAT Tester - Web Interface
Flask + SocketIO app for testing Waterstop HATs during QC.
"""

import os
import json
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'waterstop-hat-tester-2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Test history storage (in-memory, last 10)
test_history = []
MAX_HISTORY = 10

# Current test state
current_test = {
    'running': False,
    'serial': None,
    'results': [],
    'start_time': None
}

# Manual control state
manual_control = {
    'fan_on': False,
    'led_on': False,
    'gpio_tester': None
}

# Lock for thread safety
test_lock = threading.Lock()
manual_lock = threading.Lock()


def emit_update(event, data):
    """Thread-safe emit to all clients."""
    socketio.emit(event, data)


@app.route('/')
def index():
    """Serve main test page."""
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    """Get current test status."""
    return jsonify({
        'running': current_test['running'],
        'serial': current_test['serial'],
        'results': current_test['results']
    })


@app.route('/api/history')
def api_history():
    """Get test history."""
    return jsonify(test_history)


@socketio.on('connect')
def handle_connect():
    """Client connected."""
    emit('status', {
        'running': current_test['running'],
        'results': current_test['results'],
        'fan_on': manual_control['fan_on'],
        'led_on': manual_control['led_on']
    })


@socketio.on('run_test')
def handle_run_test(data):
    """Start a test run."""
    global current_test

    test_type = data.get('type', 'quick')
    serial = data.get('serial', '').strip() or None

    with test_lock:
        if current_test['running']:
            emit('error', {'message': 'Test already running'})
            return

        current_test['running'] = True
        current_test['serial'] = serial
        current_test['results'] = []
        current_test['start_time'] = datetime.now()

    emit('test_started', {'type': test_type, 'serial': serial})

    # Run test in background thread
    thread = threading.Thread(target=run_test_thread, args=(test_type, serial))
    thread.daemon = True
    thread.start()


def run_test_thread(test_type, serial):
    """Execute tests in background thread."""
    global current_test, test_history

    try:
        from gpio_tests import GPIOTester, TestResult

        # Create tester with emit callback
        tester = GPIOTester(emit_callback=emit_update)

        # Setup GPIO
        emit_update('test_update', {
            'name': 'GPIO Setup',
            'result': 'running',
            'message': 'Initializing GPIO...'
        })

        if not tester.setup():
            emit_update('test_complete', {
                'success': False,
                'message': 'GPIO initialization failed',
                'results': []
            })
            return

        emit_update('test_update', {
            'name': 'GPIO Setup',
            'result': 'pass',
            'message': 'GPIO ready'
        })

        # Run tests
        if test_type == 'full':
            results = tester.run_full_test()
        elif test_type == 'feedback':
            results = tester.run_feedback_test()
        else:
            results = tester.run_quick_test()

        # Cleanup GPIO
        tester.cleanup()

        # Process results
        result_list = []
        passed = 0
        failed = 0

        for r in results:
            result_dict = {
                'name': r.name,
                'result': r.result.value,
                'message': r.message,
                'details': r.details
            }
            result_list.append(result_dict)

            if r.result == TestResult.PASS:
                passed += 1
            elif r.result == TestResult.FAIL:
                failed += 1

        # Update current test state
        with test_lock:
            current_test['results'] = result_list
            current_test['running'] = False

        # Save to history
        history_entry = {
            'timestamp': datetime.now().isoformat(),
            'serial': serial,
            'type': test_type,
            'passed': passed,
            'failed': failed,
            'total': len(results),
            'success': failed == 0
        }

        test_history.insert(0, history_entry)
        if len(test_history) > MAX_HISTORY:
            test_history.pop()

        # Emit completion
        emit_update('test_complete', {
            'success': failed == 0,
            'passed': passed,
            'failed': failed,
            'total': len(results),
            'results': result_list
        })

    except ImportError as e:
        # Handle case where RPi.GPIO not available (dev machine)
        emit_update('test_complete', {
            'success': False,
            'message': f'GPIO library not available: {e}',
            'results': []
        })

        with test_lock:
            current_test['running'] = False

    except Exception as e:
        emit_update('test_complete', {
            'success': False,
            'message': f'Test error: {e}',
            'results': []
        })

        with test_lock:
            current_test['running'] = False


@socketio.on('stop_test')
def handle_stop_test():
    """Request to stop current test (best effort)."""
    global current_test

    with test_lock:
        if current_test['running']:
            current_test['running'] = False
            emit('test_stopped', {'message': 'Test stop requested'})


@socketio.on('toggle_fan')
def handle_toggle_fan(data):
    """Toggle fan on/off for manual testing."""
    global manual_control

    turn_on = data.get('on', False)

    with manual_lock:
        if current_test['running']:
            emit('error', {'message': 'Cannot control fan while test is running'})
            return

        try:
            from gpio_tests import GPIOTester, Pins

            # Initialize tester if needed
            if manual_control['gpio_tester'] is None:
                manual_control['gpio_tester'] = GPIOTester()
                if not manual_control['gpio_tester'].setup():
                    emit('error', {'message': 'Failed to initialize GPIO'})
                    manual_control['gpio_tester'] = None
                    return

            tester = manual_control['gpio_tester']

            if turn_on:
                tester.turn_fan_on()
                manual_control['fan_on'] = True
            else:
                tester.turn_fan_off()
                manual_control['fan_on'] = False

                # Cleanup GPIO if both fan and LED are off (safe to swap HAT)
                if not manual_control['fan_on'] and not manual_control['led_on']:
                    tester.cleanup()
                    manual_control['gpio_tester'] = None

            emit('fan_state', {'on': manual_control['fan_on']})
            socketio.emit('fan_state', {'on': manual_control['fan_on']})

        except ImportError as e:
            emit('error', {'message': f'GPIO library not available: {e}'})
        except Exception as e:
            emit('error', {'message': f'Fan control error: {e}'})


@socketio.on('toggle_led')
def handle_toggle_led(data):
    """Toggle LED on/off for manual testing."""
    global manual_control

    turn_on = data.get('on', False)

    with manual_lock:
        if current_test['running']:
            emit('error', {'message': 'Cannot control LED while test is running'})
            return

        try:
            from gpio_tests import GPIOTester, Pins

            # Initialize tester if needed
            if manual_control['gpio_tester'] is None:
                manual_control['gpio_tester'] = GPIOTester()
                if not manual_control['gpio_tester'].setup():
                    emit('error', {'message': 'Failed to initialize GPIO'})
                    manual_control['gpio_tester'] = None
                    return

            tester = manual_control['gpio_tester']

            if turn_on:
                tester.turn_led_on()
                manual_control['led_on'] = True
            else:
                tester.turn_led_off()
                manual_control['led_on'] = False

                # Cleanup GPIO if both fan and LED are off (safe to swap HAT)
                if not manual_control['fan_on'] and not manual_control['led_on']:
                    tester.cleanup()
                    manual_control['gpio_tester'] = None

            emit('led_state', {'on': manual_control['led_on']})
            socketio.emit('led_state', {'on': manual_control['led_on']})

        except ImportError as e:
            emit('error', {'message': f'GPIO library not available: {e}'})
        except Exception as e:
            emit('error', {'message': f'LED control error: {e}'})


if __name__ == '__main__':
    print("=" * 50)
    print("  WATERSTOP HAT TESTER")
    print("  Access from any browser at:")
    print("  http://<pi-ip>:8200")
    print("=" * 50)

    socketio.run(app, host='0.0.0.0', port=8200, debug=False)
