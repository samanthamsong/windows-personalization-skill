"""
Multi-device manager for Dynamic Lighting effects.

Discovers all connected DL devices (keyboards, mice, headsets, mousepads),
gets their lamp layouts, and provides a unified interface for rendering
effects across all devices simultaneously.

Usage:
    from device_manager import DeviceManager

    dm = DeviceManager(proc)  # proc = driver subprocess
    dm.discover()             # queries GET_ALL_LAYOUTS

    for device in dm.devices:
        print(f"{device.kind}: {device.lamp_count} lamps")

    # Render to all devices
    frames = {}
    for device in dm.devices:
        frame = {}
        for lamp in device.lamps:
            frame[str(lamp['idx'])] = render_color(lamp['x'], lamp['y'])
        frames[device.id] = frame
    dm.send_all(frames)
"""

import json


class Device:
    """A single Dynamic Lighting device with its lamp layout."""

    def __init__(self, data):
        self.id = data['id']
        self.name = data.get('name', 'Unknown')
        self.kind = data.get('kind', 'Unknown')
        self.lamp_count = data.get('lamp_count', 0)
        self.width_cm = data.get('width_cm', 0)
        self.height_cm = data.get('height_cm', 0)
        self.synthetic = data.get('synthetic_layout', False)

        # Normalized lamp positions (x, y in 0.0–1.0 range)
        self.lamps = []
        for lamp in data.get('lamps', []):
            if lamp.get('color_settable', True):
                self.lamps.append({
                    'idx': lamp['index'],
                    'x': lamp['x'],
                    'y': lamp['y'],
                })

    @property
    def is_keyboard(self):
        return self.kind.lower() == 'keyboard'

    @property
    def is_mouse(self):
        return self.kind.lower() == 'mouse'

    @property
    def is_mousepad(self):
        return self.kind.lower() in ('mousepad', 'mouse pad')

    @property
    def is_headset(self):
        return self.kind.lower() == 'headset'

    @property
    def is_strip(self):
        return self.kind.lower() in ('lampstrip', 'lamp strip')

    def __repr__(self):
        return f"Device({self.kind}, {len(self.lamps)} lamps, '{self.name}')"


class DeviceManager:
    """Manages multiple Dynamic Lighting devices."""

    def __init__(self, send_fn, recv_fn):
        """
        Args:
            send_fn: Function to send a command string to the driver
            recv_fn: Function to receive a response string from the driver
        """
        self.send = send_fn
        self.recv = recv_fn
        self.devices = []

    def discover(self):
        """Query the driver for all connected devices and their layouts."""
        self.send('GET_ALL_LAYOUTS')
        resp = self.recv()

        if not resp.startswith('OK '):
            print(f"  ⚠ Device discovery failed: {resp}")
            self.devices = []
            return

        try:
            data = json.loads(resp[3:])
            self.devices = [Device(d) for d in data.get('devices', [])]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"  ⚠ Failed to parse device layouts: {e}")
            self.devices = []

        if self.devices:
            for d in self.devices:
                print(f"  📱 {d.kind}: {len(d.lamps)} lamps — {d.name}")
        else:
            print("  ⚠ No Dynamic Lighting devices found")

    @property
    def keyboard(self):
        """Return the first keyboard device, or None."""
        return next((d for d in self.devices if d.is_keyboard), None)

    @property
    def all_peripherals(self):
        """Return all non-keyboard devices."""
        return [d for d in self.devices if not d.is_keyboard]

    def send_frames(self, frames):
        """Send color frames to multiple devices in one call.

        Args:
            frames: dict of device_id → {lamp_idx_str: "#hex", ...}
        """
        if not frames:
            return

        # If only one device, use faster SET_LAMPS
        if len(frames) == 1:
            device_id, frame = next(iter(frames.items()))
            self.send(f"SET_LAMPS {json.dumps(frame, separators=(',', ':'))}")
            self.recv()
        else:
            self.send(f"SET_LAMPS_MULTI {json.dumps(frames, separators=(',', ':'))}")
            self.recv()

    def send_frame_all(self, render_fn):
        """Render and send a frame to all devices using a render function.

        Args:
            render_fn: Function(device, lamp) → "#hex" color string.
                       Called for each lamp on each device.
        """
        frames = {}
        for device in self.devices:
            frame = {}
            for lamp in device.lamps:
                color = render_fn(device, lamp)
                frame[str(lamp['idx'])] = color
            frames[device.id] = frame

        self.send_frames(frames)
