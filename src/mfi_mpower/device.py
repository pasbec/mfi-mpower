"""Ubiquiti mFi MPower device"""

from __future__ import annotations

from .entities import MPowerSensor, MPowerSwitch
from .exceptions import MPowerDataError
from .interface import MPowerLED, MPowerInterface


class MPowerDevice:
    """mFi mPower device representation."""

    _data: dict = {}

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the device."""
        self.interface = MPowerInterface(host, username, password)

    async def __aenter__(self) -> MPowerDevice:
        """Enter context manager scope."""
        await self.interface.connect()
        await self.update()
        return self

    async def __aexit__(self, *kwargs) -> None:
        """Leave context manager scope."""
        await self.interface.close()

    def __str__(self) -> str:
        """Represent this device as string."""
        if self._data:
            keys = [
                "name",
                "model",
                "ports",
                "hw_version",
                "sw_version",
                "hwaddr",
                "ipaddr",
                "iface",
                "led",
            ]
        else:
            keys = ["host"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({vals})"

    @property
    def name(self) -> str:
        """Return the device name."""
        if self._data:
            return self._data.get("hostname", self.interface.host)
        return self.interface.host

    async def update(self) -> None:
        """Update sensor data."""
        self._data.update(await self.interface.get_data())

    @property
    def updated(self) -> bool:
        """Return if the device data has already been updated."""
        return bool(self._data)

    @property
    def data(self) -> dict:
        """Return device data."""
        if not self._data:
            raise MPowerDataError(
                f"Device data for device {self.name} must be updated first"
            )
        return self._data

    @property
    def manufacturer(self) -> str:
        """Return the device manufacturer."""
        return "Ubiquiti"

    @property
    def hostname(self) -> str:
        """Return the device host name."""
        return self.data["status"]["hostname"]
    
    @property
    def iface(self) -> str: 
        """Return the device network interface."""
        return self.data["status"]["iface"].upper()

    @property
    def ipaddr(self) -> str:
        """Return the device IP address."""
        return self.data["status"]["ipaddr"]

    @property
    def hwaddr(self) -> str:
        """Return the main device hardware address."""
        return self.data["board"]["hwaddr"]

    @property
    def sw_version(self) -> str:
        """Return the device firmware version."""
        status = self.data["status"]
        version = status["firmware_version"]
        build = status["firmware_build"]
        return f"{version} (build {build})"

    @property
    def hw_version(self) -> str:
        """Return the device hardware revision."""
        return self.data["board"]["revision"]

    @property
    def eu_model(self) -> bool | None:
        """Return whether this device is a EU model with type F sockets."""
        shortname = self.data["board"]["shortname"]
        if len(shortname) > 2 and shortname.endswith("E"):
            return True
        elif len(shortname) > 1:
            return False
        return None

    @property
    def model(self) -> str:
        """Return if the model."""
        name = self.data["board"]["name"]
        eu_tag = " (EU)" if self.eu_model else ""
        if name:
            return f"mFi {name}{eu_tag}"
        return ""

    @property
    def model_id(self) -> str:
        """Return if the model id."""
        return self.data["board"]["sysid"]

    @property
    def led(self) -> MPowerLED:
        """Return if the led status."""
        return self.data["status"]["led"]

    async def set_led(self, led: MPowerLED, refresh: bool = True) -> None:
        """Set LED state to on/off."""
        if self.led == MPowerLED.LOCKED_OFF:
            await self.interface.run(f"echo {MPowerLED.OFF.value} > /proc/led/status")
        await self.interface.run(f"echo {led.value} > /proc/led/status")
        if refresh:
            await self.update()

    @property
    def ports(self) -> int:
        """Return the number of available ports."""
        return self.data["board"]["ports"]

    @property
    def description(self) -> str:
        """Return the device description as string."""
        ports = self.ports
        if ports == 1:
            return "mFi Power Adapter with Wi-Fi"
        if ports == 3:
            return "3-Port mFi Power Strip with Wi-Fi"
        if ports == 6:
            return "6-Port mFi Power Strip with Ethernet and Wi-Fi"
        if ports == 8:
            return "8-Port mFi Power Strip with Ethernet and Wi-Fi"
        return ""

    @property
    def unique_id(self) -> str:
        """Return a unique device id from combined LAN/WLAN hardware addresses."""
        return f"{self.data['hwaddr']['lan']}-{self.data['hwaddr']['wlan']}"

    async def create_sensor(self, port: int) -> MPowerSensor:
        """Create a single sensor."""
        if not self.updated:
            await self.update()
        return MPowerSensor(self, port)

    async def create_sensors(self) -> list[MPowerSensor]:
        """Create all sensors as list."""
        if not self.updated:
            await self.update()
        return [MPowerSensor(self, i + 1) for i in range(self.ports)]

    async def create_switch(self, port: int) -> MPowerSwitch:
        """Create a single switch."""
        if not self.updated:
            await self.update()
        return MPowerSwitch(self, port)

    async def create_switches(self) -> list[MPowerSwitch]:
        """Create all switches as list."""
        if not self.updated:
            await self.update()
        return [MPowerSwitch(self, i + 1) for i in range(self.ports)]
