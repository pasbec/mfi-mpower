"""Ubiquiti mFi MPower SSH interface"""

from __future__ import annotations

from enum import Enum


class MPowerLED(Enum):
    """mFi mPower LED status representation."""

    OFF = 0
    BLUE = 1
    YELLOW = 2
    BOTH = 3
    ALTERNATE = 4
    LOCKED_OFF = 99  # <turn OFF to unlock>

    def __str__(self):
        return self.name


class MPowerNetwork(Enum):
    """mFi mPower network interface representation."""

    LAN = 0
    WLAN = 1

    @classmethod
    def from_dev(cls, s: str) -> "MPowerNetwork":
        s = s.lower()
        if s.startswith("eth"):
            return cls.LAN
        else:
            return cls.WLAN

    def __str__(self):
        return self.name