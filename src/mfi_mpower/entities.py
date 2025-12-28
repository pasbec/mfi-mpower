"""Ubiquiti mFi MPower entities"""

from __future__ import annotations

from . import device
from .exceptions import MPowerDataError
from .interface import MPowerInterface


class MPowerEntity:
    """mFi mPower entity representation."""

    _data: dict
    _device: device.MPowerDevice
    _port: int

    def __init__(
        self,
        device: device.MPowerDevice,
        port: int,
    ) -> None:
        """Initialize the entity."""
        self._data = {}
        self._device = device
        self._port = port
        self.update(device.data)

    def __str__(self):  
        """Represent this entity as string."""
        keys = ["name", "label"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({vals})"

    def update(self, data: dict) -> None:
        """Update entity data from given **device data**."""
        try:
            self._data.update(data.get("ports", [])[self.port - 1])
        except IndexError as exc:
            raise MPowerDataError(
                f"Device data for entity {self.name} is invalid"
            ) from exc

    async def refresh(self) -> None:
        """Refresh entity data from **device data**."""
        await self.device.refresh()
        self.update(self.device.data)

    @property
    def data(self) -> dict:
        """Return entity data."""
        return self._data

    @property
    def has_data(self) -> bool:
        """Return whether the entity has data."""
        return bool(self._data)

    @property
    def device(self) -> device.MPowerDevice:
        """Return the entity device."""
        return self._device

    @property
    def port(self) -> int:
        """Return the entity port."""
        return self._port

    @property
    def host(self) -> str:
        """Return the entity host."""
        return self.device.host

    @property
    def name(self) -> str:
        """Return the device name."""
        return f"{self.device.name}-{self.port}"

    @property
    def interface(self) -> MPowerInterface:
        """Return the device interface."""
        return self.device.interface

    @property
    def label(self) -> str | None:
        """Return the entity label."""
        return self.data.get("config", {}).get("label")

    @property
    def output(self) -> bool | None:
        """Return the current output state."""
        return self.data.get("sensors", {}).get("output")

    @property
    def relay(self) -> bool | None:
        """Return the initial output state which is applied after device boot."""
        return self.data.get("sensors", {}).get("relay")

    @property
    def locked(self) -> bool | None:
        """Return the lock state which prevents switching if enabled."""
        return self.data.get("sensors", {}).get("locked")

    async def set_lock(self, locked: bool, refresh: bool = True) -> None:
        """Set lock state to on/off."""
        await self.interface.set_port_lock(self.port, locked)
        if refresh:
            await self.refresh()

    async def lock(self, refresh: bool = True) -> None:
        """Lock output switch."""
        await self.set_lock(True, refresh=refresh)

    async def unlock(self, refresh: bool = True) -> None:
        """Unlock output switch."""
        await self.set_lock(False, refresh=refresh)

class MPowerSensor(MPowerEntity):
    """mFi mPower sensor representation."""

    def __str__(self):
        """Represent this sensor as string."""
        keys = ["name", "label", "power", "current", "voltage", "powerfactor", "energy"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({vals})"

    @property
    def power(self) -> float | None:
        """Return the output power [W]."""
        return self.data.get("sensors", {}).get("power")

    @property
    def current(self) -> float | None:
        """Return the output current [A]."""
        return self.data.get("sensors", {}).get("current")

    @property
    def voltage(self) -> float | None:
        """Return the output voltage [V]."""
        return self.data.get("sensors", {}).get("voltage")

    @property
    def powerfactor(self) -> float | None:
        """Return the output power factor ("real power" / "apparent power")."""
        return self.data.get("sensors", {}).get("powerfactor")

    @property
    def energy(self) -> float | None:
        """Return the energy since last device boot [Wh]."""
        return self.data.get("sensors", {}).get("energy")


class MPowerSwitch(MPowerEntity):
    """mFi mPower switch representation."""

    def __str__(self):
        """Represent this switch as string."""
        keys = ["name", "label", "output", "relay", "locked"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({vals})"

    async def set_output(self, output: bool, refresh: bool = True) -> None:
        """Set output to on/off."""
        await self.interface.set_port_output(self.port, output)
        if refresh:
            await self.refresh()

    async def turn_on(self, refresh: bool = True) -> None:
        """Turn output on."""
        await self.set_output(True, refresh=refresh)

    async def turn_off(self, refresh: bool = True) -> None:
        """Turn output off."""
        await self.set_output(False, refresh=refresh)
        
    async def toggle(self, refresh: bool = True) -> None:
        """Toggle output."""
        await self.set_output(not self.output, refresh=refresh)
