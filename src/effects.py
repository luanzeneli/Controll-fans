"""Animation / effect engine.

Each Effect knows how to produce a list of (r,g,b) colours for a device with N
LEDs at a given moment in time. The engine is deliberately framework-agnostic:
the GUI calls `engine.tick()` on a timer (~30x/second) and the engine pushes the
freshly computed colours to every selected device via the RGBClient.

Effects:
  - StaticEffect      solid colour
  - BreathingEffect   fade a colour in and out
  - RainbowEffect     rainbow that scrolls across the LEDs
  - WaveEffect        a moving band of colour
  - ColorCycleEffect  whole device smoothly cycles through the hue wheel
  - TemperatureEffect reactive: colour mapped from a live value (e.g. CPU temp)
  - AudioEffect       reactive: brightness/colour follows audio level
"""

from __future__ import annotations

import colorsys
import math
from typing import Callable, List, Tuple

RGB = Tuple[int, int, int]


def hsv_to_rgb(h: float, s: float, v: float) -> RGB:
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, s, v)
    return int(r * 255), int(g * 255), int(b * 255)


def scale(color: RGB, factor: float) -> RGB:
    factor = max(0.0, min(1.0, factor))
    return tuple(int(c * factor) for c in color)  # type: ignore


class Effect:
    """Base class. Subclasses implement frame()."""

    name = "effect"

    def __init__(self, color: RGB = (255, 255, 255), speed: float = 1.0,
                 brightness: float = 1.0):
        self.color = color
        self.speed = speed          # multiplier; 1.0 = normal
        self.brightness = brightness  # 0..1

    def frame(self, t: float, led_count: int) -> List[RGB]:
        """Return led_count colours for time t (seconds)."""
        raise NotImplementedError


class StaticEffect(Effect):
    name = "Static"

    def frame(self, t, led_count):
        return [scale(self.color, self.brightness)] * led_count


class BreathingEffect(Effect):
    name = "Breathing"

    def frame(self, t, led_count):
        # sine wave 0..1
        phase = (math.sin(t * self.speed * 2) + 1) / 2
        return [scale(self.color, phase * self.brightness)] * led_count


class RainbowEffect(Effect):
    name = "Rainbow"

    def frame(self, t, led_count):
        out = []
        for i in range(led_count):
            hue = (i / max(led_count, 1)) + t * self.speed * 0.2
            out.append(hsv_to_rgb(hue, 1.0, self.brightness))
        return out


class WaveEffect(Effect):
    name = "Wave"

    def frame(self, t, led_count):
        out = []
        for i in range(led_count):
            # a moving brightness band along the strip
            phase = math.sin((i / max(led_count, 1)) * math.pi * 2
                             - t * self.speed * 3)
            phase = (phase + 1) / 2
            out.append(scale(self.color, phase * self.brightness))
        return out


class ColorCycleEffect(Effect):
    name = "Color Cycle"

    def frame(self, t, led_count):
        hue = (t * self.speed * 0.1) % 1.0
        return [hsv_to_rgb(hue, 1.0, self.brightness)] * led_count


class TemperatureEffect(Effect):
    """Maps a live 0..1 value (set externally each tick) to a blue->red gradient.

    The GUI feeds `self.value` from a TempMonitor. 0 = cool/blue, 1 = hot/red.
    """

    name = "Temperature"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.value = 0.0  # updated externally, 0..1

    def frame(self, t, led_count):
        v = max(0.0, min(1.0, self.value))
        # hue 0.66 (blue) -> 0.0 (red)
        hue = 0.66 * (1 - v)
        return [hsv_to_rgb(hue, 1.0, self.brightness)] * led_count


class AudioEffect(Effect):
    """Brightness follows a live 0..1 audio level (set externally each tick).

    Hue slowly drifts so it doesn't look static during quiet passages.
    """

    name = "Audio Reactive"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.level = 0.0  # updated externally, 0..1

    def frame(self, t, led_count):
        v = max(0.0, min(1.0, self.level))
        hue = (t * self.speed * 0.05) % 1.0
        base = hsv_to_rgb(hue, 1.0, 1.0)
        return [scale(base, v * self.brightness)] * led_count


# Registry so the GUI can list available effects by name.
EFFECTS = {
    e.name: e for e in [
        StaticEffect, BreathingEffect, RainbowEffect, WaveEffect,
        ColorCycleEffect, TemperatureEffect, AudioEffect,
    ]
}


class EffectEngine:
    """Drives one active effect across a set of target devices."""

    def __init__(self, client):
        self.client = client
        self.effect: Effect | None = None
        self.target_indices: List[int] = []  # which devices to animate
        self._t = 0.0

    def set_effect(self, effect: Effect, targets: List[int]):
        self.effect = effect
        self.target_indices = targets
        self._t = 0.0
        # Direct mode is required for streamed colours to show (esp. MSI boards)
        for idx in targets:
            try:
                self.client.set_direct_mode(idx)
            except Exception:
                pass

    def clear(self):
        self.effect = None

    def tick(self, dt: float):
        """Advance the animation by dt seconds and push to hardware."""
        if self.effect is None or not self.client.connected:
            return
        self._t += dt
        for idx in self.target_indices:
            if idx >= len(self.client.devices):
                continue
            n = self.client.devices[idx].led_count
            if n == 0:
                continue
            colors = self.effect.frame(self._t, n)
            try:
                self.client.set_led_colors(idx, colors)
            except Exception:
                # a device may disconnect mid-animation; skip it this frame
                pass
