"""Ubiquiti mFi MPower device"""
from __future__ import annotations

import re

from .session import MPowerSession
from .entities import MPowerSensor, MPowerSwitch
from .exceptions import MPowerDataError


class MPowerDevice:
    """mFi mPower device representation."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the device."""
        self.host = host
        self.username = username
        self.password = password
        self.session = MPowerSession(host, username, password)

        self._data = {}

    async def __aenter__(self) -> MPowerDevice:
        """Enter context manager scope."""
        await self.session.connect()
        await self.update()
        return self

    async def __aexit__(self, *kwargs) -> None:
        """Leave context manager scope."""
        await self.session.close()

    def __str__(self) -> str:
        """Represent this device as string."""
        if self._data:
            keys = [
                "name",
                "ipaddr",
                "iface",
                "hwaddr",
                "model",
                "ports",
                "fwversion",
            ]
        else:
            keys = ["host"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({vals})"

    @property
    def name(self) -> str:
        """Return the device name."""
        if self._data:
            return self._data.get("hostname", self.host)
        return self.host

    async def update(self) -> None:
        """Update sensor data."""
        # Initialize data
        data = {}
            
        try:
            # Update static data
            if not self._data:
                # Read host name
                data["hostname"] = await self.session.run("cat /proc/sys/kernel/hostname")

                # Read interface and IP address
                iface = await self.session.run("ip route | awk '/default/ {print $5}'")
                data["ipaddr"] = await self.session.run(f"ifconfig {iface} | awk '/inet / {{print $2}}' | cut -d: -f2")
                data["iface"] = "lan" if iface.startswith("eth") else "wlan"

                # Read hardware address
                iface_hwaddr = await self.session.run("ifconfig -a | awk '/^[a-z]/ {iface=$1} /HWaddr/ {print iface, $NF}'")
                iface_hwaddr = {m[0]: m[1] for m in [v.split() for v in iface_hwaddr.splitlines()] if ":" in m[1]}
                for iface, hwaddr in iface_hwaddr.items():
                    if iface.startswith("eth"):
                        data.setdefault("hwaddr", {})["lan"] = hwaddr
                    else:
                        data.setdefault("hwaddr", {})["wlan"] = hwaddr

                # Read firmware version and build
                data["fwversion"] = f"v{await self.session.run('cat /usr/etc/.version')}"
                data["fwbuild"] = await self.session.run("cat /usr/etc/.build")

                # Read board data
                board_info = await self.session.run("cat /etc/board.info")
                data["board"] =dict(
                    (m.group(1), m.group(2))
                    for m in re.finditer(r"board.(\w+)=(.*)", board_info)
                )

                # Determine number of ports
                ports = int(data["board"]["shortname"][1])
            else:
                ports = self.ports

            # Initialize port data
            data["ports"] = [{"port": i+1} for i in range(ports)]

            # Read port config
            for key, get in {
                "label": {"name": "config_file", "grep": "label", "cast": str},
                # "enabled": {"name": "vpower_cfg", "grep": "enabled", "cast": lambda x: bool(int(x))},
                # "lock": {"name": "vpower_cfg", "grep": "lock", "cast": lambda x: bool(int(x))},
                # "relay": {"name": "vpower_cfg", "grep": "relay", "cast": lambda x: bool(int(x))},
            }.items():
                command = f"cat /etc/persistent/cfg/{get['name']} | grep {get['grep']} | sort"
                values = [v.split("=")[1].strip() for v in (await self.session.run(command)).splitlines()]
                for i, value in enumerate(values):
                    data["ports"][i][key] = get["cast"](value)

            # Read port sensor data
            for key, get in {
                "current": {"name": "i_rms", "cast": float},  # current [A]
                "enabled": {"name": "enabled", "cast": lambda x: bool(int(x))},  # enabled state
                "energy": {"name": "energy_sum", "cast": float},  # energy [Wh]
                "locked": {"name": "lock", "cast": lambda x: bool(int(x))},  # lock state
                "output": {"name": "output", "cast": lambda x: bool(int(x))},  # output state
                "power": {"name": "active_pwr", "cast": float},  # power [W]
                "powerfactor": {"name": "pf", "cast": float},  # power factor
                "relay": {"name": "relay", "cast": lambda x: bool(int(x))},  # relay state
                "voltage": {"name": "v_rms", "cast": float},  # voltage [V]
            }.items():
                command = f"cat /proc/power/{get['name']}*"
                values = [v.strip() for v in (await self.session.run(command)).splitlines()]
                for i, value in enumerate(values):
                    data["ports"][i][key] = get["cast"](value)

        except Exception as exc:
            raise MPowerDataError(
                f"Data from device {self.session.host} is not valid: {type(exc).__name__}({exc})"
            ) from exc

        # Update data
        self._data.update(data)

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
        return self.data["hostname"]
    
    @property
    def iface(self) -> str: 
        """Return the device network interface."""
        return self.data["iface"]

    @property
    def ipaddr(self) -> str:
        """Return the device IP address."""
        return self.data["ipaddr"]

    @property
    def hwaddr(self) -> str:
        """Return the device hardware address from LAN if connected, else from WLAN."""
        if self.iface == "lan":
            return self.data["hwaddr"]["lan"]
        return self.data["hwaddr"]["wlan"]

    @property
    def fwversion(self) -> str:
        """Return the device host firmware version."""
        return self.data["fwversion"]

    @property
    def fwbuild(self) -> str:
        """Return the device host firmware version."""
        return self.data["fwbuild"]

    @property
    def sysid(self) -> str:
        """Return if the board id."""
        return self.data["board"]["sysid"]

    @property
    def cpurevision(self) -> str:
        """Return if the board CPU revision."""
        return self.data["board"]["cpurevision"]

    @property
    def revision(self) -> str:
        """Return if the board revision."""
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
        """Return if the board model."""
        name = self.data["board"]["name"]
        eu_tag = " (EU)" if self.eu_model else ""
        if name:
            return name + eu_tag
        return ""

    @property
    def ports(self) -> int:
        """Return the number of available ports for the board device."""
        shortname = self.data["board"]["shortname"]
        return int(shortname[1])

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
