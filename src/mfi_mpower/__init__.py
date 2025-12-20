"""This is the mFi mPower module."""
from __future__ import annotations

from .exceptions import MPowerError, MPowerDataError
from .session import MPowerConnectionError, MPowerAuthenticationError, MPowerCommandError
from .device import MPowerDevice
from .entities import MPowerSensor, MPowerSwitch

__version__ = "2.1.2"
