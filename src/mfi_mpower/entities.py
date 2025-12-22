"""Ubiquiti mFi MPower entities"""

from __future__ import annotations

from . import device  # pylint: disable=unused-import
from .exceptions import MPowerDataError


class MPowerEntity:
    """mFi mPower entity representation."""

    def __init__(
        self,
        device: device.MPowerDevice,  # pylint: disable=redefined-outer-name
        port: int,
    ) -> None:
        """Initialize the entity."""
        self.device = device
        self.port = port

        if not device.updated:
            raise MPowerDataError(f"Device {device.name} must be updated first")

        self._data = device.port_data[self.port - 1]

        if port < 1:
            raise ValueError(
                f"Port number {port} for device {device.name} is too small: 1-{device.ports}"
            )
        if port > device.ports:
            raise ValueError(
                f"Port number {port} for device {device.name} is too large: 1-{device.ports}"
            )

    def __str__(self):
        """Represent this entity as string."""
        name = f"name={self.device.name}"
        keys = ["port", "label"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({name}, {vals})"

    async def update(self) -> None:
        """Update entity data from device data."""
        await self.device.update()
        self._data = self.device.port_data[self.port - 1]

    @property
    def data(self) -> dict:
        """Return entity data."""
        return self._data

    @data.setter
    def data(self, value: dict) -> None:
        """Set entity data."""
        self._data = value
    
    @property
    def unique_id(self) -> str:
        """Return unique entity id from unique device id and port."""
        return f"{self.device.unique_id}-{self.port}"

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
        await self.device.interface.set_port_lock(self.port, locked)
        if refresh:
            await self.update()

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
        name = f"name={self.device.name}"
        keys = ["port", "label", "power", "current", "voltage", "powerfactor", "energy"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({name}, {vals})"

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
        name = f"name={self.device.name}"
        keys = ["port", "label", "output", "relay", "locked"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({name}, {vals})"

    async def set_output(self, output: bool, refresh: bool = True) -> None:
        """Set output to on/off."""
        await self.device.interface.set_port_output(self.port, output)
        if refresh:
            await self.update()

    async def turn_on(self, refresh: bool = True) -> None:
        """Turn output on."""
        await self.set_output(True, refresh=refresh)

    async def turn_off(self, refresh: bool = True) -> None:
        """Turn output off."""
        await self.set_output(False, refresh=refresh)
    async def toggle(self, refresh: bool = True) -> None:
        """Toggle output."""
        await self.set_output(not self.output, refresh=refresh)
