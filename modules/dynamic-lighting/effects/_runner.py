"""
Shared effect runner for multi-device Dynamic Lighting effects.
================================================================
Provides EffectRunner — handles driver launch, multi-device discovery,
animation loop with pause-file alert coordination, and cleanup.

Usage:
    from _runner import EffectRunner, lerp

    runner = EffectRunner("My Effect")

    def render_frame(device, t):
        colors = {}
        for lamp in device.lamps:
            colors[str(lamp['idx'])] = '#ff0000'
        return colors

    runner.run(render_frame, fps=8)

For CREATE_EFFECT wrapper scripts:
    runner = EffectRunner("Rainbow")
    runner.send("CREATE_EFFECT wave ...")
    runner.recv()
    runner.keep_alive()
"""

import os
import sys
import subprocess
import json
import time
import threading
import signal
import atexit
import math

# Import DeviceManager from the spotify module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'spotify'))
from device_manager import DeviceManager

EXE = os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.join(os.path.expanduser('~'), 'AppData', 'Local')),
    'DynamicLightingDriver', 'DynamicLightingDriver.exe'
)

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')


def lerp(c1, c2, t):
    """Linearly interpolate between two RGB tuples."""
    t = max(0.0, min(1.0, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def hex_color(r, g, b):
    """Format RGB tuple as hex color string."""
    return '#{:02x}{:02x}{:02x}'.format(
        max(0, min(255, int(r))),
        max(0, min(255, int(g))),
        max(0, min(255, int(b))))


class EffectRunner:
    """Manages driver lifecycle, multi-device discovery, and animation loop."""

    def __init__(self, name="Effect"):
        if not os.path.isfile(EXE):
            print(f"Error: Driver not found at {EXE}", file=sys.stderr)
            sys.exit(1)

        self.proc = subprocess.Popen(
            [EXE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        # Drain stderr to prevent blocking
        threading.Thread(
            target=lambda: [self.proc.stderr.readline() for _ in iter(int, 1)],
            daemon=True,
        ).start()

        # Register cleanup
        atexit.register(self._cleanup)
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
        except (OSError, ValueError):
            pass

        # Wait for driver ready
        ready = self.recv()
        if ready != 'READY':
            print(f"Error: Driver not ready: {ready}", file=sys.stderr)
            self.proc.terminate()
            sys.exit(1)

        # Set effect name in the driver UI
        self.send(f"SET_EFFECT_NAME {name}")
        self.recv()

        # Ensure device availability via foreground hold
        self.send("HOLD_FOREGROUND on")
        self.recv()

        # Discover all connected devices
        self.dm = DeviceManager(self.send, self.recv)
        self.dm.discover()

        if not self.dm.devices:
            print("No Dynamic Lighting devices found.", file=sys.stderr)
            self.proc.terminate()
            sys.exit(1)

        self.name = name
        self._last_effect_cmd = None

    def send(self, cmd):
        """Send a command to the driver."""
        self.proc.stdin.write((cmd + '\n').encode())
        self.proc.stdin.flush()

    def recv(self):
        """Read a response from the driver."""
        line = self.proc.stdout.readline()
        if not line:
            return None
        return line.decode().strip()

    def run(self, render_fn, fps=8):
        """Run the animation loop across all devices.

        Args:
            render_fn: Function(device, t) → {lamp_idx_str: '#rrggbb'}
                       Called once per device per frame.
            fps: Target frames per second (default 8).
        """
        device_count = len(self.dm.devices)
        lamp_count = sum(len(d.lamps) for d in self.dm.devices)
        print(f"Starting {self.name} on {device_count} device(s), "
              f"{lamp_count} lamps (~{fps}fps). Press Ctrl+C to stop.",
              flush=True)

        frame = 0
        start = time.time()
        try:
            while True:
                # Alert flash coordination
                if os.path.exists(PAUSE_FILE):
                    self._handle_alert_flash(frame)
                    continue

                t = time.time() - start
                frames = {}
                for device in self.dm.devices:
                    frames[device.id] = render_fn(device, t)
                self.dm.send_frames(frames)

                frame += 1
                target = frame / float(fps)
                elapsed = time.time() - start
                if target > elapsed:
                    time.sleep(target - elapsed)
        except KeyboardInterrupt:
            print("\nStopped.", flush=True)
        finally:
            self._cleanup()

    def keep_alive(self, effect_cmd=None):
        """Keep the driver process alive for CREATE_EFFECT wrapper scripts.

        Handles alert flash coordination with multi-device support.
        After a flash, re-sends the effect command to resume.

        Args:
            effect_cmd: The CREATE_EFFECT command string to re-send after alerts.
        """
        if effect_cmd:
            self._last_effect_cmd = effect_cmd

        print(f"Running {self.name} (driver PID {self.proc.pid}). "
              f"Press Ctrl+C to stop.", flush=True)

        try:
            while True:
                if os.path.exists(PAUSE_FILE):
                    self._handle_alert_flash(0)
                    # Resume the driver-side effect
                    if self._last_effect_cmd:
                        self.send(self._last_effect_cmd)
                        self.recv()
                    continue
                if self.proc.poll() is not None:
                    break
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            self._cleanup()

    def _handle_alert_flash(self, frame):
        """Flash all devices for a notification alert."""
        try:
            with open(PAUSE_FILE, 'r') as f:
                alert_data = f.read().strip()
            parts = alert_data.split('|')
            flash_color = parts[0] if parts[0].startswith('#') else '#FF69B4'
            flash_duration = float(parts[1]) if len(parts) > 1 else 3.0
            flash_start = time.time()
            while time.time() - flash_start < flash_duration:
                self.dm.send_frame_all(lambda dev, lamp: flash_color)
                time.sleep(0.125)
        except Exception as e:
            print(f"Alert flash error: {e}")
        finally:
            try:
                os.remove(PAUSE_FILE)
            except Exception:
                pass

    def _signal_handler(self, signum, frame):
        self._cleanup()
        sys.exit(0)

    def _cleanup(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
