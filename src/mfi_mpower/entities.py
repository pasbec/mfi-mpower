"""Ubiquiti mFi MPower entities"""
from __future__ import annotations

from . import device  # pylint: disable=unused-import
from .exceptions import MPowerAPIDataError


class MPowerEntity:
    """mFi mPower entity representation."""

    def __init__(
        self,
        device: device.MPowerDevice,  # pylint: disable=redefined-outer-name
        port: int,
    ) -> None:
        """Initialize the entity."""
        self._device = device
        self._port = port

        if not device.updated:
            raise MPowerAPIDataError(f"Device {device.name} must be updated first")

        self._data = device.port_data[self._port - 1]

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
        name = f"name={self._device.name}"
        keys = ["port", "label"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({name}, {vals})"

    async def update(self) -> None:
        """Update entity data from device data."""
        await self._device.update()
        self._data = self._device.port_data[self._port - 1]

    @property
    def device(self) -> device.MPowerDevice:
        """Return the entity device."""
        return self._device

    @property
    def data(self) -> dict:
        """Return all entity data."""
        return self._data

    @data.setter
    def data(self, data: dict) -> None:
        """Set entity data."""
        self._data = data

    @property
    def unique_id(self) -> str:
        """Return unique entity id from unique device id and port."""
        return f"{self.device.unique_id}-{self.port}"

    @property
    def port(self) -> int:
        """Return the port number (starting with 1)."""
        return int(self._port)

    @property
    def label(self) -> str:
        """Return the entity label."""
        return str(self._data.get("label", ""))

    @property
    def output(self) -> bool:
        """Return the current output state."""
        return bool(self._data["output"])

    @property
    def relay(self) -> bool:
        """Return the initial output state which is applied after device boot."""
        return bool(self._data["relay"])

    @property
    def lock(self) -> bool:
        """Return the output lock state which prevents switching if enabled."""
        return bool(self._data["lock"])


class MPowerSensor(MPowerEntity):
    """mFi mPower sensor representation."""

    precision: dict[str, float | None] = {
        "power": None,
        "current": None,
        "voltage": None,
        "powerfactor": None,
    }

    def __str__(self):
        """Represent this sensor as string."""
        name = f"name={self._device.name}"
        keys = ["port", "label", "power", "current", "voltage", "powerfactor", "energy"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({name}, {vals})"

    def _value(self, key: str, scale: float = 1.0) -> float | None:
        """Process (scale and round) and return sensor value."""
        value = self._data.get(key)
        if value is not None:
            value *= scale
            precision = self.precision.get(key, None)
            if precision is not None:
                value = round(value, precision)
        return value

    @property
    def power(self) -> float | None:
        """Return the output power [W]."""
        return self._value("power")

    @property
    def current(self) -> float | None:
        """Return the output current [A]."""
        return self._value("current")

    @property
    def voltage(self) -> float | None:
        """Return the output voltage [V]."""
        return self._value("voltage")

    @property
    def powerfactor(self) -> float | None:
        """Return the output power factor ("real power" / "apparent power") [%]."""
        # NOTE: Raw data is dimensionless factor between 0 and 1
        return self._value("powerfactor", scale=100)

    @property
    def energy(self) -> float | None:
        """Return the energy (of this month) [kWh]."""
        # NOTE: Raw data is dimensionless impulse counter with 3200 imp/kWh
        return self._value("thismonth", scale=1/3200)


class MPowerSwitch(MPowerEntity):
    """mFi mPower switch representation."""

    def __str__(self):
        """Represent this switch as string."""
        name = f"name={self._device.name}"
        keys = ["port", "label", "output", "relay", "lock"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({name}, {vals})"

    async def set(self, output: bool, refresh: bool = True) -> None:
        """Set output to on/off."""
        await self._device.request(
            "POST", "/mfi/sensors.cgi", data={"id": self._port, "output": int(output)}
        )
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
        output = not bool(self._data["output"])
        await self.set(output, refresh=refresh)
