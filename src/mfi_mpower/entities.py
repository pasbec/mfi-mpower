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

        self._data = device.data["ports"][self.port - 1]

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
        self._data = self.device.data["ports"][self.port - 1]

    @property
    def data(self) -> dict:
        """Return all entity data."""
        return self._data
    
    @property
    def unique_id(self) -> str:
        """Return unique entity id from unique device id and port."""
        return f"{self.device.unique_id}-{self.port}"

    @property
    def label(self) -> str:
        """Return the entity label."""
        label = str(self.data["label"])
        if label:
            return label
        return f"Port {self.port}"

    @property
    def output(self) -> bool:
        """Return the current output state."""
        return bool(self.data["output"])

    @property
    def relay(self) -> bool:
        """Return the initial output state which is applied after device boot."""
        return bool(self.data["relay"])

    @property
    def locked(self) -> bool:
        """Return the lock state which prevents switching if enabled."""
        return bool(self.data["locked"])

    async def lock(self) -> None:
        """Lock output switch."""
        await self.device.session.run(f"echo 1 > /proc/power/lock{self.port}")
        await self.update()

    async def unlock(self) -> None:
        """Unlock output switch."""
        await self.device.session.run(f"echo 0 > /proc/power/lock{self.port}")
        await self.update()

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
        return self.data.get("power")

    @property
    def current(self) -> float | None:
        """Return the output current [A]."""
        return self.data.get("current")

    @property
    def voltage(self) -> float | None:
        """Return the output voltage [V]."""
        return self.data.get("voltage")

    @property
    def powerfactor(self) -> float | None:
        """Return the output power factor ("real power" / "apparent power")."""
        return self.data.get("powerfactor")

    @property
    def energy(self) -> float | None:
        """Return the energy since last device boot [Wh]."""
        return self.data.get("energy")


class MPowerSwitch(MPowerEntity):
    """mFi mPower switch representation."""

    def __str__(self):
        """Represent this switch as string."""
        name = f"name={self.device.name}"
        keys = ["port", "label", "output", "relay", "locked"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({name}, {vals})"

    async def set(self, output: bool, refresh: bool = True) -> None:
        """Set output to on/off."""
        await self.device.session.run(f"echo {int(output)} > /proc/power/output{self.port}")
        if refresh:
            await self.update()

    async def turn_on(self, refresh: bool = True) -> None:
        """Turn output on."""
        await self.set(True, refresh=refresh)

    async def turn_off(self, refresh: bool = True) -> None:
        """Turn output off."""
        await self.set(False, refresh=refresh)

    async def toggle(self, refresh: bool = True) -> None:
        """Toggle output."""
        await self.update()
        await self.set(not self.output, refresh=refresh)
