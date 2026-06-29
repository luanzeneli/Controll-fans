"""Live data sources for reactive effects.

TempMonitor  - reads CPU (and GPU if available) temperature via psutil.
AudioMonitor - captures system/mic audio level via sounddevice.

Both run on a background thread and expose a single normalised float in [0,1]
that the GUI samples each frame. Both fail soft: if the dependency or hardware
isn't available they just report 0.0 instead of crashing the app.
"""

from __future__ import annotations

import threading
import time

try:
    import psutil
except ImportError:
    psutil = None

try:
    import numpy as np
    import sounddevice as sd
except ImportError:
    np = None
    sd = None


class TempMonitor:
    """Tracks CPU temperature, normalised to 0..1 between min/max bounds."""

    def __init__(self, min_c: float = 30.0, max_c: float = 85.0, poll: float = 1.0):
        self.min_c = min_c
        self.max_c = max_c
        self.poll = poll
        self.value = 0.0          # normalised 0..1
        self.celsius = 0.0        # raw reading
        self._running = False
        self._thread: threading.Thread | None = None

    def available(self) -> bool:
        return psutil is not None and hasattr(psutil, "sensors_temperatures")

    def _read_celsius(self) -> float:
        if psutil is None:
            return 0.0
        try:
            temps = psutil.sensors_temperatures()
        except Exception:
            return 0.0
        if not temps:
            return 0.0
        # Prefer a CPU-ish sensor, otherwise take the hottest reading we find.
        preferred = ("k10temp", "coretemp", "zenpower", "cpu_thermal")
        for key in preferred:
            if key in temps and temps[key]:
                return max(s.current for s in temps[key])
        hottest = 0.0
        for entries in temps.values():
            for s in entries:
                if s.current:
                    hottest = max(hottest, s.current)
        return hottest

    def _loop(self):
        while self._running:
            c = self._read_celsius()
            self.celsius = c
            span = max(self.max_c - self.min_c, 1.0)
            self.value = max(0.0, min(1.0, (c - self.min_c) / span))
            time.sleep(self.poll)

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False


class AudioMonitor:
    """Tracks audio input loudness (RMS), smoothed and normalised to 0..1.

    By default it opens the system default input device. On Linux you can route
    your speaker output into an input (a PulseAudio/PipeWire 'monitor' source)
    so the lights react to whatever is playing, not just the mic.
    """

    def __init__(self, sensitivity: float = 8.0, smoothing: float = 0.6):
        self.sensitivity = sensitivity   # higher = more reactive
        self.smoothing = smoothing       # 0..1, higher = smoother/slower
        self.level = 0.0
        self._stream = None

    def available(self) -> bool:
        return sd is not None and np is not None

    def _callback(self, indata, frames, time_info, status):  # noqa: ARG002
        if np is None:
            return
        rms = float(np.sqrt(np.mean(indata ** 2)))
        scaled = min(1.0, rms * self.sensitivity)
        # exponential smoothing so the lights don't strobe harshly
        self.level = self.smoothing * self.level + (1 - self.smoothing) * scaled

    def start(self):
        if not self.available() or self._stream is not None:
            return
        try:
            self._stream = sd.InputStream(channels=1, callback=self._callback)
            self._stream.start()
        except Exception:
            self._stream = None

    def stop(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._stream = None
        self.level = 0.0
