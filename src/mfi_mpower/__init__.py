"""This is the mFi mPower module."""
from __future__ import annotations

from .device import MPowerDevice
from .entities import MPowerEntity, MPowerSensor, MPowerSwitch
from .exceptions import MPowerError, MPowerDataError
from .interface import MPowerLED, MPowerIface
from .session import MPowerConnectionError, MPowerAuthenticationError, MPowerCommandError

__version__ = "2.4.6"
