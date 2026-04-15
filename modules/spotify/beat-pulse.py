"""
Standalone beat-pulse lighting — no Spotify needed.

Pulses ALL connected RGB devices to the beat of whatever audio is playing
on the system (any app, any source). Just pick a color.

Works with keyboards, mice, headsets, mousepads — any Dynamic Lighting device.

Usage:
    python beat-pulse.py pink
    python beat-pulse.py "#FF69B4"
    python beat-pulse.py red --sensitivity 1.3
    python beat-pulse.py "hot pink" --secondary cyan

Named colors: red, blue, green, pink, purple, cyan, orange, yellow,
              white, magenta, coral, lavender, teal, gold, hotpink
"""

import os
import sys
import json
import math
import time
import signal
import subprocess
import threading

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, MODULE_DIR)

from color_extract import rgb_to_hex
from mood_mapper import apply_brightness, blend_colors
from device_manager import DeviceManager

# Driver exe path
DRIVER_EXE = os.path.join(MODULE_DIR, '..', 'dynamic-lighting', 'src',
                          'DynamicLightingDriver', 'bin', 'Debug',
                          'net9.0-windows10.0.26100.0', 'DynamicLightingDriver.exe')

# Named color map
COLOR_MAP = {
    'red':       (255, 50, 50),
    'blue':      (50, 80, 255),
    'green':     (50, 220, 80),
    'pink':      (255, 105, 180),
    'hotpink':   (255, 60, 150),
    'hot pink':  (255, 60, 150),
    'purple':    (160, 50, 255),
    'cyan':      (0, 220, 255),
    'orange':    (255, 140, 30),
    'yellow':    (255, 220, 50),
    'white':     (255, 255, 255),
    'magenta':   (255, 0, 180),
    'coral':     (255, 120, 100),
    'lavender':  (180, 130, 255),
    'teal':      (0, 180, 180),
    'gold':      (255, 200, 50),
}


def parse_color(s):
    """Parse a color name or hex string into (r, g, b) tuple."""
    s = s.strip().lower()

    # Named color
    if s in COLOR_MAP:
        return COLOR_MAP[s]

    # Hex color: #FF69B4 or FF69B4
    hex_str = s.lstrip('#')
    if len(hex_str) == 6:
        try:
            r = int(hex_str[0:2], 16)
            g = int(hex_str[2:4], 16)
            b = int(hex_str[4:6], 16)
            return (r, g, b)
        except ValueError:
            pass

    print(f"⚠  Unknown color '{s}'. Using pink.")
    return (255, 105, 180)


def render_lamp_color(x, y, t, primary, secondary, beat_phase, volume):
    """Render color for a single lamp at normalized position (x, y).

    Works for any device — keyboard, mouse, headset, mousepad.
    """
    # Volume-reactive base brightness — always follows the music
    vol_brightness = 0.05 + volume * 0.85

    # Beat flash: extra burst on top of volume
    pulse = max(0.0, 1.0 - beat_phase * 2.0)
    pulse = pulse ** 0.4
    beat_boost = pulse * 0.6
    brightness = min(1.0, vol_brightness + beat_boost)

    beat_count = int(t * 2) % 2

    # Radial burst from center
    cx, cy = 0.5, 0.5
    dist = math.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_dist = math.sqrt(0.5 ** 2 + 0.5 ** 2)
    norm_dist = dist / max_dist

    # Ripple ring expanding outward on beat
    ripple = max(0.0, 1.0 - abs(norm_dist - beat_phase * 0.8) * 4.0)

    # Blend primary ↔ secondary based on distance
    if secondary:
        frac = (norm_dist + beat_count * 0.5) % 1.0
        base = blend_colors(primary, secondary, frac)
    else:
        base = primary

    local_brightness = min(1.0, brightness + ripple * 0.5)
    color = apply_brightness(base, local_brightness)
    return rgb_to_hex(*color)


class BeatPulse:
    def __init__(self, primary, secondary=None, sensitivity=1.4, cooldown=0.12):
        self.primary = primary
        self.secondary = secondary
        self.sensitivity = sensitivity
        self.cooldown = cooldown
        self.running = False
        self.proc = None
        self.dm = None
        self.beat_detector = None

    def start_driver(self):
        if not os.path.exists(DRIVER_EXE):
            print(f"ERROR: Driver not found at {DRIVER_EXE}")
            print("Run: dotnet build modules/dynamic-lighting/DynamicLightingDriver.sln")
            sys.exit(1)

        self.proc = subprocess.Popen(
            [DRIVER_EXE],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0
        )
        threading.Thread(
            target=lambda: [self.proc.stderr.readline() for _ in iter(int, 1)],
            daemon=True
        ).start()

        ready = self.proc.stdout.readline().decode().strip()
        if ready != 'READY':
            print(f"ERROR: Driver not ready: {ready}")
            sys.exit(1)

    def send(self, cmd):
        self.proc.stdin.write((cmd + '\n').encode())
        self.proc.stdin.flush()

    def recv(self):
        return self.proc.stdout.readline().decode().strip()

    def run(self):
        self.start_driver()

        # Discover all connected devices
        print("🔍 Discovering devices...")
        self.dm = DeviceManager(self.send, self.recv)
        self.dm.discover()

        if not self.dm.devices:
            print("ERROR: No Dynamic Lighting devices found")
            sys.exit(1)

        # Set effect name
        color_name = next(
            (name for name, rgb in COLOR_MAP.items()
             if rgb == self.primary and name != 'hot pink'),
            rgb_to_hex(*self.primary)
        )
        effect_name = f"Beat Pulse ({color_name})"
        self.send(f'SET_EFFECT_NAME {effect_name}')
        self.recv()

        # Start beat detector
        try:
            from beat_detect import BeatDetector
            self.beat_detector = BeatDetector(
                sensitivity=self.sensitivity,
                cooldown=self.cooldown
            )
            self.beat_detector.start()
            print("🥁 Beat detection active (Windows audio meter)")
        except Exception as e:
            print(f"ERROR: Beat detection failed: {e}")
            print("Make sure audio is playing and pycaw is installed:")
            print("  pip install pycaw comtypes numpy")
            sys.exit(1)

        self.running = True
        sec_str = f" + {rgb_to_hex(*self.secondary)}" if self.secondary else ""
        print(f"🎨 Color: {rgb_to_hex(*self.primary)}{sec_str}")
        print(f"🔊 Sensitivity: {self.sensitivity}, Cooldown: {self.cooldown}s")
        device_count = len(self.dm.devices)
        print(f"💡 Pulsing {device_count} device(s) to the beat — play any music! (Ctrl+C to stop)")
        print()

        frame_count = 0
        start_time = time.time()
        last_beat = time.time()

        try:
            while self.running:
                now = time.time()
                t = now - start_time

                if self.beat_detector.wait_for_beat(timeout=0.001):
                    last_beat = now

                beat_phase = min(1.0, (now - last_beat) / 0.5)
                volume = self.beat_detector.current_peak

                # Render to all devices using normalized coordinates
                primary, secondary = self.primary, self.secondary
                self.dm.send_frame_all(
                    lambda dev, lamp: render_lamp_color(
                        lamp['x'], lamp['y'], t, primary, secondary, beat_phase, volume
                    )
                )

                frame_count += 1
                target = frame_count / 30.0
                elapsed = now - start_time
                if target > elapsed:
                    time.sleep(target - elapsed)

        except KeyboardInterrupt:
            print("\n⏹  Stopping beat pulse...")
        finally:
            self.running = False
            if self.beat_detector:
                self.beat_detector.stop()
            if self.proc:
                try:
                    self.send('QUIT')
                except Exception:
                    pass
                self.proc.terminate()


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Standalone beat-pulse lighting effect',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python beat-pulse.py pink
  python beat-pulse.py "#FF69B4"
  python beat-pulse.py red --secondary cyan
  python beat-pulse.py purple --sensitivity 1.2

Named colors: """ + ', '.join(sorted(COLOR_MAP.keys()))
    )
    parser.add_argument('color', help='Primary color (name or #hex)')
    parser.add_argument('--secondary', '-s', help='Secondary color for blending')
    parser.add_argument('--sensitivity', type=float, default=1.4,
                        help='Beat sensitivity (lower=more sensitive, default: 1.4)')
    parser.add_argument('--cooldown', type=float, default=0.12,
                        help='Min seconds between beats (default: 0.12)')

    args = parser.parse_args()
    primary = parse_color(args.color)
    secondary = parse_color(args.secondary) if args.secondary else None

    bp = BeatPulse(
        primary=primary,
        secondary=secondary,
        sensitivity=args.sensitivity,
        cooldown=args.cooldown
    )

    def sigint_handler(sig, frame):
        bp.running = False
    signal.signal(signal.SIGINT, sigint_handler)

    bp.run()


if __name__ == '__main__':
    main()
