"""
Real-time beat detection via Windows audio meter.

Uses pycaw IAudioMeterInformation to read system audio peak levels
and detect beats from energy spikes. No raw audio capture needed —
just reads the peak meter from the default output device.
"""

import threading
import time
import numpy as np

from pycaw.pycaw import AudioUtilities, IAudioMeterInformation
from comtypes import CLSCTX_ALL


class BeatDetector:
    """Detects beats from system audio peak meter."""

    def __init__(self, sensitivity=1.5, cooldown=0.15):
        """
        Args:
            sensitivity: Peak spike threshold vs rolling average (1.0 = any, 2.0 = strong only)
            cooldown: Minimum seconds between beat detections
        """
        self.sensitivity = sensitivity
        self.cooldown = cooldown
        self.running = False
        self._thread = None
        self._lock = threading.Lock()

        self._beat_event = threading.Event()
        self._last_beat_time = 0.0
        self._beat_intensity = 0.0
        self._current_peak = 0.0

        self._peak_history = []
        self._history_len = 50  # ~1 second at 50Hz polling

    @property
    def beat_intensity(self):
        """Last detected beat intensity (0.0–1.0)."""
        with self._lock:
            return self._beat_intensity

    @property
    def current_peak(self):
        """Current audio peak level (0.0–1.0), updated at 50Hz."""
        with self._lock:
            return self._current_peak

    def wait_for_beat(self, timeout=0.5):
        """Block until next beat or timeout. Returns True if beat detected."""
        self._beat_event.clear()
        return self._beat_event.wait(timeout=timeout)

    def start(self):
        """Start monitoring audio levels."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        time.sleep(0.2)
        if not self.running:
            raise RuntimeError("Beat detection failed to start")

    def _run(self):
        """Audio meter polling loop."""
        try:
            import comtypes
            comtypes.CoInitialize()

            speakers = AudioUtilities.GetSpeakers()
            device = speakers._dev
            interface = device.Activate(IAudioMeterInformation._iid_, CLSCTX_ALL, None)
            meter = interface.QueryInterface(IAudioMeterInformation)

            while self.running:
                peak = meter.GetPeakValue()

                with self._lock:
                    self._current_peak = peak
                    self._peak_history.append(peak)
                    if len(self._peak_history) > self._history_len:
                        self._peak_history.pop(0)

                    if len(self._peak_history) < 10:
                        time.sleep(0.02)
                        continue

                    avg = np.mean(self._peak_history)
                    if avg < 0.001:
                        time.sleep(0.02)
                        continue

                    now = time.time()
                    ratio = peak / avg

                    if ratio > self.sensitivity and (now - self._last_beat_time) > self.cooldown:
                        self._last_beat_time = now
                        self._beat_intensity = min(1.0, (ratio - 1.0) / 2.0)
                        self._beat_event.set()

                time.sleep(0.02)  # 50Hz polling

        except Exception as e:
            print(f"  ⚠ Beat detection error: {e}")
            print("  ℹ Beat sync disabled — falling back to timed animation")
            self.running = False
        finally:
            try:
                import comtypes
                comtypes.CoUninitialize()
            except Exception:
                pass

    def stop(self):
        """Stop monitoring."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
