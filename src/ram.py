"""Direct RGB control for Kingston Fury Beast DDR5 over the SMBus.

OpenRGB can't detect/control this RAM, so we talk to the sticks' dedicated RGB
controller chips directly. Each stick has an RGB controller on the I801 SMBus
(bus 0) at a fixed address (0x61, 0x63). We write a short documented register
sequence to set a static colour — the controller then holds it on its own
(unlike the motherboard's Direct-mode fans, RAM colour persists without
streaming, until changed or a reboot).

SAFETY: we only ever touch addresses 0x61/0x63 — the RGB chips — never the
PMIC (~0x48) or SPD (0x50+). Worst case from these registers is a wrong colour.

Permissions: writing to /dev/i2c-0 needs the user to be in the `i2c` group
(`sudo usermod -aG i2c $USER` then re-login). Without it, available() is False
and the GUI hides RAM control with a hint.
"""

from __future__ import annotations

import time
from typing import List, Tuple

try:
    from smbus2 import SMBus
except ImportError:
    SMBus = None

RGB = Tuple[int, int, int]

DEFAULT_BUS = 0           # SMBus I801 (confirmed via `i2cdetect -l`)
DEFAULT_ADDRS = [0x61, 0x63]  # one RGB controller per stick (2 sticks)

# Register sequence for Kingston Fury Beast DDR5 RGB controllers.
REG_BEGIN = 0x08
REG_MODE = 0x09
REG_RED = 0x31
REG_GREEN = 0x32
REG_BLUE = 0x33
REG_BRIGHTNESS = 0x20
VAL_BEGIN = 0x53
VAL_MODE_STATIC = 0x00
VAL_COMMIT = 0x44
WRITE_DELAY = 0.02        # 20ms between writes, per the controller's timing


class RAMController:
    """Sets a static colour on Kingston Fury DDR5 sticks via the SMBus."""

    def __init__(self, bus: int = DEFAULT_BUS, addrs: List[int] = None):
        self.bus_num = bus
        self.addrs = addrs if addrs is not None else list(DEFAULT_ADDRS)

    def available(self) -> bool:
        """True if smbus2 is installed and we can open the bus (permissions)."""
        if SMBus is None:
            return False
        try:
            bus = SMBus(self.bus_num)
            bus.close()
            return True
        except Exception:
            return False

    def unavailable_reason(self) -> str:
        if SMBus is None:
            return "The 'smbus2' package isn't installed (pip install smbus2)."
        try:
            SMBus(self.bus_num).close()
            return ""
        except PermissionError:
            return ("No permission to access /dev/i2c-%d.\n"
                    "Run:  sudo usermod -aG i2c $USER\n"
                    "then log out and back in (or reboot)." % self.bus_num)
        except Exception as exc:
            return f"Couldn't open SMBus {self.bus_num}: {exc}"

    def set_color(self, color: RGB, brightness: int = 0x32) -> None:
        """Set both sticks to one static colour. brightness 0x00-0x63."""
        if SMBus is None:
            raise RuntimeError("smbus2 not installed")
        r, g, b = (max(0, min(255, int(c))) for c in color)
        brightness = max(0, min(0x63, int(brightness)))
        with SMBus(self.bus_num) as bus:
            for addr in self.addrs:
                self._w(bus, addr, REG_BEGIN, VAL_BEGIN)
                self._w(bus, addr, REG_MODE, VAL_MODE_STATIC)
                self._w(bus, addr, REG_RED, r)
                self._w(bus, addr, REG_GREEN, g)
                self._w(bus, addr, REG_BLUE, b)
                self._w(bus, addr, REG_BRIGHTNESS, brightness)
                self._w(bus, addr, REG_BEGIN, VAL_COMMIT)

    def turn_off(self) -> None:
        self.set_color((0, 0, 0))

    def _w(self, bus, addr: int, reg: int, val: int) -> None:
        bus.write_byte_data(addr, reg, val)
        time.sleep(WRITE_DELAY)
