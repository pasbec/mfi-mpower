"""Ubiquiti mFi MPower device"""

from __future__ import annotations

from typing import Any

from .entities import MPowerSensor, MPowerSwitch
from .enums import MPowerLED, MPowerNetwork
from .interface import MPowerInterface


class MPowerDevice:
    """mFi mPower device representation."""

    _data: dict
    _interface: MPowerInterface

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the device."""
        self._data = {}
        self._interface = MPowerInterface(host, username, password)

    async def __aenter__(self) -> MPowerDevice:
        """Enter context manager scope."""
        await self.interface.connect()
        await self.refresh()
        return self

    async def __aexit__(self, *kwargs) -> None:
        """Leave context manager scope."""
        await self.interface.close()

    def __str__(self) -> str:
        """Represent this device as string."""
        if self.has_data:
            keys = [
                "name",
                "model",
                "ports",
                "revision",
                "firmware",
                "mac",
                "ip",
                "network",
                "led",
            ]
            # keys += [
            #     "host",
            #     "manufacturer",
            #     "model_id",
            #     "description",
            #     "is_eu_model",
            #     "macs",
            #     "hostname",
            # ]
        else:
            keys = ["host"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({vals})"

    def update(self, data: dict) -> None:
        """Update device from given data."""
        self._data.update(data)

    async def refresh(self) -> None:
        """Refresh device data."""
        data = await self.interface.get_data()
        self._data.update(data)

    @property
    def data(self) -> dict[str, Any]:
        """Return device data."""
        return self._data or {}

    @property
    def has_data(self) -> bool:
        """Return whether the device has data."""
        return bool(self._data)

    @property
    def interface(self) -> MPowerInterface:
        """Return device interface."""
        return self._interface

    @property
    def host(self) -> str:
        """Return the device host."""
        return self.interface.host

    @property
    def name(self) -> str:
        """Return the device name."""
        return self.hostname

    @property
    def board_data(self) -> dict[str, Any]:
        """Return the device board data."""
        return self.data.get("board", {})

    @property
    def status_data(self) -> dict[str, Any]:
        """Return the device status data."""
        return self.data.get("status", {})

    @property
    def port_data(self) -> list[dict[str, Any]]:
        """Return port data."""
        return self.data.get("ports", [])

    @property
    def manufacturer(self) -> str:
        """Return the device manufacturer."""
        return "Ubiquiti"

    @property
    def model_id(self) -> str | None:
        """Return the model id."""
        return self.board_data.get("sysid")

    @property
    def ports(self) -> int | None:
        """Return the number of available ports."""
        return self.board_data.get("ports")

    @property
    def description(self) -> str | None:
        """Return the device description as string."""
        ports = self.ports
        if ports:
            if ports == 1:
                return "mFi Power Adapter with Wi-Fi"
            if ports == 3:
                return "3-Port mFi Power Strip with Wi-Fi"
            if ports == 6:
                return "6-Port mFi Power Strip with Ethernet and Wi-Fi"
            if ports == 8:
                return "8-Port mFi Power Strip with Ethernet and Wi-Fi"
        return None

    @property
    def is_eu_model(self) -> bool | None:
        """Return whether this device is a EU model with type F sockets."""
        shortname: str | None = self.board_data.get("shortname")
        if shortname:
            if len(shortname) > 2 and shortname.endswith("E"):
                return True
            elif len(shortname) > 1:
                return False
        return None

    @property
    def model(self) -> str | None:
        """Return the model name."""
        name = self.board_data.get("name")
        eu_tag = " (EU)" if self.is_eu_model else ""
        if name:
            return f"mFi {name}{eu_tag}"
        return None

    @property
    def revision(self) -> str | None:
        """Return the device hardware revision."""
        return self.board_data.get("revision")

    @property
    def mac(self) -> str | None:
        """Return the hardware address from the board."""
        return self.board_data.get("hwaddr")

    @property
    def macs(self) -> list[str] | None:
        """Return hardware addresses from network interfaces."""
        return self.board_data.get("hwaddrs")

    @property
    def firmware(self) -> str | None:
        """Return the device firmware version and build."""
        version = self.status_data.get("firmware_version")
        build = self.status_data.get("firmware_build")
        if build is None:
            return version
        elif version is not None:
            return f"{version} (build {build})"
        return None

    @property
    def hostname(self) -> str:
        """Return the device host name."""
        return self.status_data.get("hostname", self.host)
    
    @property
    def network(self) -> MPowerNetwork | None: 
        """Return the device network interface."""
        return self.status_data.get("iface")

    @property
    def ip(self) -> str | None:
        """Return the device IP address."""
        return self.status_data.get("ipaddr")

    @property
    def led(self) -> MPowerLED | None:
        """Return if the led status."""
        return self.status_data.get("led")

    async def set_led(self, led: MPowerLED, refresh: bool = True) -> None:
        """Set LED state to on/off."""
        await self.interface.set_led(led)
        if refresh:
            await self.refresh()

    async def create_sensor(self, port: int) -> MPowerSensor:
        """Create a single sensor."""
        if not self.has_data:
            await self.refresh()
        return MPowerSensor(self, port)

    async def create_sensors(self) -> list[MPowerSensor]:
        """Create all sensors as list."""
        if not self.has_data:
            await self.refresh()
        return [MPowerSensor(self, i + 1) for i in range(self.ports)]

    async def create_switch(self, port: int) -> MPowerSwitch:
        """Create a single switch."""
        if not self.has_data:
            await self.refresh()
        return MPowerSwitch(self, port)

    async def create_switches(self) -> list[MPowerSwitch]:
        """Create all switches as list."""
        if not self.has_data:
            await self.refresh()
        return [MPowerSwitch(self, i + 1) for i in range(self.ports)]
