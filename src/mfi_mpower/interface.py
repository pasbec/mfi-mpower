"""Ubiquiti mFi MPower SSH interface"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import KeysView, ValuesView
from enum import Enum
import json
import re
from typing import Any, Callable

from .session import MPowerSession


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


class MPowerCat(ABC):
    """mFi mPower cat interface base."""

    dir: str | None = None
    file: str | None = None
    func: type | Callable = str

    def __init__(
        self,
        session: MPowerSession,
    ) -> None:
        """Initialize the cat interface."""
        self.session = session

    @property
    @abstractmethod
    def specs(self) -> dict:
        """Return the specs."""
        pass

    def keys(self) -> KeysView:
        """Return the keys."""
        return self.specs.keys()

    def values(self) -> ValuesView:
        """Return the specs values."""
        return self.specs.values()

    def files(self) -> list[str]:
        """Return the specs files."""
        return [v.get("file", self.file).format(dir=self.dir) for v in self.values()]

    def command(self) -> str:
        """Return the cat command with ASCII Record Separator (0x1E) for file separation."""
        commands = ["cd /tmp"]
        commands += [c for v in self.specs.values() if (c := v.get("command", None))]
        commands += [r"printf '\x1E' > _",  fr"cat {' _ '.join(self.files())}"]
        return " && ".join(commands)

    def convert(self, key: str, values: list[str]) -> Any:
        """Convert cat output values for one spec."""
        func = self.specs[key].get("func", self.func)
        return func(values)

    async def get_data(self) -> dict[str, list[str]]:
        """Run the cat command and parse the output into a data dictionary."""
        keys = list(self.keys())
        async with self.session.get(self.command()) as output:
            outputs = output.split("\x1E")  # Split by separation markers
            groups = {keys[i]: o.splitlines() for i, o in enumerate(outputs)}
            data = {k: self.convert(k, v) for k, v in groups.items()}
            for key in [k for k in keys if self.specs[k].get("unwrap", False)]:
                if isinstance(data[key], dict):  # Flatten (unwrap) only dicts
                    data = {**{kk: vv for kk, vv in data.items() if kk != key}, **data[key]}
            return data
    

class MPowerCatBoard(MPowerCat):
    """mFi mPower cat interface for board information."""

    PORTS = {
        "0xe641": 1,
        "0xe651": 1,
        "0xe671": 1,
        "0xe672": 1,
        "0xe662": 2,
        "0xe643": 3,
        "0xe653": 3,
        "0xe656": 6,
        "0xe648": 8,
    }

    def func_info(self, values: list[str]) -> dict[str, str]:
        """Extract board information."""
        data = {
            match.group(1): match.group(2)
            for value in values
            if (match := re.match(r"^board.(\w+)=(.*)", value))
        }
        data["ports"] = int(self.PORTS[data["sysid"].lower()])
        hwaddr = data.pop("hwaddr")
        data["hwaddr"] = ':'.join(hwaddr[i:i+2] for i in range(0, 12, 2))
        return data

    def func_ifconfig(self, values: list[str]) -> dict[str, str]:
        """Extract hardware addresses from ifconfig output."""
        data = {
            "hwaddr_lan" if match.group(1).startswith("eth") else "hwaddr_wlan": match.group(2)
            for value in values
            if (match := re.match(r"^([a-zA-Z0-9]+).*?HWaddr ([0-9A-Fa-f:]{17})", value))
        }
        return data
    
    @property
    def specs(self):
        """Return the specs."""
        return {
            "info": {"file": "/etc/board.info", "func": self.func_info, "unwrap": True},
            "ifconfig": {
                "file": "ifconfig",
                "command": "ifconfig -a > ifconfig",
                "func": self.func_ifconfig,
                "unwrap": True
            },
        }
    

class MPowerCatStatus(MPowerCat):
    """mFi mPower cat interface for status information."""

    def func(self, values: list[str]) -> str:
        """Unwrap value."""
        return values[0]

    def func_led_status(self, values: list[str]) -> MPowerLED:
        """Unwrap value and convert to LED status enum type."""
        return MPowerLED(int(values[0].split()[0]))
    
    def func_ip_route(self, values: list[str]) -> dict[str, str]:
        """Extract network interface and IP address from 'ip route' output."""
        data = {
            "iface": match.group(1)
            for value in values
            if (match := re.match(r"^default.* dev (\S+)", value))
        }
        data.update({
            "ipaddr": match.group(1)
            for value in values
            if (match := re.search(fr"dev {data.get('iface')}.*src (\d+\.\d+\.\d+\.\d+)", value))
        })
        data["iface"] = "lan" if data["iface"].startswith("eth") else "wlan"
        return data
    
    @property
    def specs(self):
        """Return the specs."""
        return {
            "firmware_version": {"file": "/usr/etc/.version"},
            "firmware_build": {"file": "/usr/etc/.build",},
            "led": {"file": "/proc/led/status", "func": self.func_led_status},
            "hostname": {"file": "/proc/sys/kernel/hostname"},
            "ip_route": {
                "file": "ip_route",
                "command": "ip route > ip_route",
                "func": self.func_ip_route,
                "unwrap": True
            },
        }
    

class MPowerCatPort(MPowerCat):
    """mFi mPower cat interface base for ports."""

    def __init__(
        self,
        session: MPowerSession,
        ports: int,
    ) -> None:
        """Initialize the port cat processor."""
        super().__init__(session)
        self.ports = ports


class MPowerCatPortConfig(MPowerCatPort):
    """mFi mPower cat interface for port config data."""

    dir = "/etc/persistent/cfg"

    def func_label(self, values: list[str]) -> list[str]:
        """Convert labels."""
        data = {
            int(match.group(1)): match.group(2)
            for value in values
            if (match := re.match(r"port\.(\d+)\.label=(.*)", value))
        }
        label = [data.get(i, None) for i in range(self.ports)]
        return label

    def func_vpower(self, values: list[str]) -> dict[str, bool]:
        """Convert vpower settings."""
        vpower = {}
        for setting in ("enabled", "lock", "relay"):
            data = {
                int(match.group(1))-1: match.group(2)
                for value in values
                if (match := re.match(fr"vpower\.(\d+)\.{setting}=(.*)", value))
            }
            vpower[setting] = [data.get(i, None) for i in range(self.ports)]
        return vpower
    
    @property
    def specs(self):
        """Return the specs."""
        return {
            "label": {"file": "{dir}/config_file", "func": self.func_label},
            "vpower": {"file": "{dir}/vpower_cfg", "func": self.func_vpower, "unwrap": True},
        }
    

class MPowerCatPortSensors(MPowerCatPort):
    """mFi mPower cat interface for port sensor data."""

    dir = "/proc/power"

    def func_float(self, values: list[str]) -> list[float]:
        """Convert float readings."""
        return [float(value) for value in values]

    def func_bool(self, values: list[str]) -> list[bool]:
        """Convert boolean readings."""
        return [bool(int(value)) for value in values]
    
    @property
    def specs(self):
        """Return the specs."""
        return {
            "energy": {"file": "{dir}/energy_sum*", "func": self.func_float},  # energy [Wh]
            "voltage": {"file": "{dir}/v_rms*", "func": self.func_float},  # voltage [V]
            "current": {"file": "{dir}/i_rms*", "func": self.func_float},  # current [A]
            "power": {"file": "{dir}/active_pwr*", "func": self.func_float},  # power [W]
            "powerfactor": {"file": "{dir}/pf*", "func": self.func_float},  # power factor
            "output": {"file": "{dir}/output*", "func": self.func_bool},  # output state
            "enabled": {"file": "{dir}/enabled*", "func": self.func_bool},  # enabled state
            "locked": {"file": "{dir}/lock*", "func": self.func_bool},  # lock state
            "relay": {"file": "{dir}/relay*", "func": self.func_bool},  # relay state
        }


class MPowerInterface:
    """mFi mPower interface representation."""

    _board: dict | None = None

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the interface."""
        self.session = MPowerSession(host, username, password)

    @staticmethod
    def value(
        string: str,
        read: Callable | None = None,
        cast: type | Callable | None = None
    ) -> Any:
        """Cast a value to a specific type."""
        if cast is None:
            cast = str
        try:
            return cast((string if read is None else read(string)).strip())
        except ValueError:
            return None

    @property
    def host(self) -> None:
        """Return session host."""
        return self.session.host
        
    async def connect(self) -> None:
        """Establish connection."""
        await self.session.connect()
        
    async def close(self) -> None:
        """Close connection."""
        await self.session.close()
        
    async def run(self, command) -> None:
        """Run command without returning output."""
        await self.session.run(command)

    async def get_board(self) -> dict:
        """Get (stored) board info."""
        if self._board is None:
            self._board = await MPowerCatBoard(self.session).get_data()
        return self._board

    async def get_status_info(self) -> dict:
        """Get device status information."""
        return await MPowerCatStatus(self.session).get_data()

    async def get_ports(self) -> int:
        """Get number of ports from board info."""
        return (await self.get_board())["ports"]

    async def get_port_data_from_cat(self, cat: MPowerCatPort) -> list[dict]:
        """Get port data from template."""
        data = await cat.get_data()
        return [{k: v for k, v in zip(data, values)} for values in zip(*data.values())]

    async def get_port_config_data(self) -> list[dict]:
        """Get port config data."""
        ports = await self.get_ports()
        return await self.get_port_data_from_cat(MPowerCatPortConfig(self.session, ports))

    async def get_port_sensor_data(self) -> list[dict]:
        """Get port sensor data."""
        ports = await self.get_ports()
        return await self.get_port_data_from_cat(MPowerCatPortSensors(self.session, ports))

    async def get_port_data(self) -> list[dict]:
        """Get port data."""
        ports = await self.get_ports()
        config = await self.get_port_config_data()
        sensors = await self.get_port_sensor_data()
        return [{"config": config[i], "sensors": sensors[i]} for i in range(ports)]

    async def get_data(self, debug: bool = False) -> dict:
        """Get all data."""
        data = {
            "board": await self.get_board(),
            "status": await self.get_status_info(),
            "ports": await self.get_port_data(),
        }
        
        if debug:
            print("data", "=", json.dumps(data, indent=2, default=str))

        return data
