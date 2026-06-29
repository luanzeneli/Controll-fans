"""Thin wrapper around the OpenRGB SDK.

OpenRGB is the engine that actually talks to the RGB chips on your fans,
RAM and cooler. It exposes a local TCP "SDK server" (default 127.0.0.1:6742).
This module hides the OpenRGB API behind a few simple methods the rest of the
app uses, so the GUI never touches the raw protocol.

Colour values throughout the app are plain (r, g, b) tuples, 0-255.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor, DeviceType
except ImportError:  # pragma: no cover - lets the GUI show a friendly message
    OpenRGBClient = None
    RGBColor = None
    DeviceType = None

RGB = Tuple[int, int, int]


@dataclass
class Device:
    """A simplified view of one OpenRGB device (a fan, RAM stick, AIO, etc.)."""

    index: int
    name: str
    type: str
    led_count: int
    # one (name, current_size) per zone; ARGB zones (fan headers) are resizable
    zones: List[Tuple[str, int]] = field(default_factory=list)
    handle: object = field(repr=False, default=None)


class RGBClient:
    """Connects to OpenRGB and pushes colours to devices."""

    def __init__(self, host: str = "127.0.0.1", port: int = 6742,
                 name: str = "MyRGBApp"):
        self.host = host
        self.port = port
        self.name = name
        self._client = None
        self.devices: List[Device] = []

    # -- connection ---------------------------------------------------------

    @property
    def connected(self) -> bool:
        return self._client is not None

    def connect(self) -> None:
        """Open the connection and enumerate devices.

        Raises RuntimeError with a human-readable message on failure so the
        GUI can show it directly.
        """
        if OpenRGBClient is None:
            raise RuntimeError(
                "The 'openrgb-python' package isn't installed.\n"
                "Run: pip install -r requirements.txt"
            )
        try:
            self._client = OpenRGBClient(self.host, self.port, self.name)
        except Exception as exc:  # connection refused, etc.
            self._client = None
            raise RuntimeError(
                "Couldn't reach the OpenRGB SDK server.\n\n"
                "Make sure OpenRGB is running with its server enabled:\n"
                "    openrgb --server\n\n"
                f"(technical detail: {exc})"
            ) from exc
        self._reload_devices()

    def _reload_devices(self) -> None:
        self.devices = []
        for i, dev in enumerate(self._client.devices):
            zones = [(z.name, len(z.leds)) for z in getattr(dev, "zones", [])]
            self.devices.append(
                Device(
                    index=i,
                    name=dev.name,
                    type=str(getattr(dev, "type", "")).split(".")[-1].title(),
                    led_count=len(dev.leds),
                    zones=zones,
                    handle=dev,
                )
            )

    # -- device configuration ----------------------------------------------

    def set_direct_mode(self, index: int) -> None:
        """Put a device into Direct mode so streamed colours actually show.

        On boards like the MSI Z790 this is the only mode that works on Linux,
        so we force it before streaming any effect.
        """
        dev = self.devices[index].handle
        for mode in getattr(dev, "modes", []):
            if "direct" in mode.name.lower():
                try:
                    dev.set_mode(mode)
                except Exception:
                    pass
                return

    def resize_zone(self, index: int, zone_index: int, size: int) -> None:
        """Set how many LEDs an addressable zone (e.g. a JRAINBOW fan header) has.

        ARGB headers can't auto-report their LED count, so we tell OpenRGB how
        many are daisy-chained on each one. OpenRGB remembers this.
        """
        dev = self.devices[index].handle
        zone = dev.zones[zone_index]
        try:
            zone.resize(int(size))
        except Exception as exc:
            raise RuntimeError(f"Couldn't resize zone '{zone.name}': {exc}") from exc
        self._reload_devices()

    def rescan(self) -> None:
        """Ask OpenRGB to re-detect devices (e.g. after plugging something in)."""
        if not self.connected:
            return
        try:
            self._client.update()
        except Exception:
            pass
        self._reload_devices()

    # -- writing colours ----------------------------------------------------

    def set_device_color(self, index: int, color: RGB) -> None:
        """Set every LED on one device to a single colour."""
        dev = self.devices[index].handle
        dev.set_color(RGBColor(*color))

    def set_led_colors(self, index: int, colors: List[RGB]) -> None:
        """Set per-LED colours on one device. `colors` length should match
        the device's led_count; it's padded/truncated to be safe."""
        device = self.devices[index]
        n = device.led_count
        if len(colors) < n:
            colors = colors + [colors[-1] if colors else (0, 0, 0)] * (n - len(colors))
        colors = colors[:n]
        rgb_objs = [RGBColor(*c) for c in colors]
        # fast=True batches the update for smooth animation
        device.handle.set_colors(rgb_objs, fast=True)

    def set_all(self, color: RGB) -> None:
        """Set every device to one solid colour."""
        for d in self.devices:
            d.handle.set_color(RGBColor(*color))

    def turn_off(self) -> None:
        self.set_all((0, 0, 0))

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
        self._client = None
