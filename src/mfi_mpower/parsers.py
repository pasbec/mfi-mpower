"""Ubiquiti mFi MPower parsers"""

from __future__ import annotations

from abc import ABC, abstractmethod
import re
from typing import Any, Callable, ItemsView, KeysView, ValuesView

from .enums import MPowerLED, MPowerNetwork
from .session import MPowerSession


class MPowerDataParser(ABC):
    """mFi mPower data parser base."""

    _session: MPowerSession

    separator: str = "\x1E"  # ASCII record output separator
    boundary: str = " \t\r\n"  # Output boundary characters

    def __init__(
        self,
        session: MPowerSession,
    ) -> None:
        """Initialize the parser."""
        self._session = session

    @property
    def session(self) -> MPowerSession:
        """Return the session."""
        return self._session

    @property
    def dir(self) -> str | None:
        """Return the default directory."""
        return None

    @property
    def file(self) -> str | None:
        """Return the default file."""
        return None

    @property
    def func(self) -> type | Callable:
        """Return the default conversion function."""
        return str

    @property
    @abstractmethod
    def specs(self) -> dict[str, dict[str, Any]]:
        """Return the parser specs."""
        pass

    def cast(self, value: str, to: type) -> Any:
        """Cast value to given type, returning None on failure."""
        if value is None:
            return None
        try:
            return to(value)
        except (ValueError, TypeError):
            return None

    def keys(self) -> KeysView:
        """Return the parser spec keys."""
        return self.specs.keys()

    def values(self) -> ValuesView:
        """Return the parser spec values."""
        return self.specs.values()

    def items(self) -> ItemsView:
        """Return the parser spec items."""
        return self.specs.items()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Return the parser spec for the given key."""
        return self.specs.get(key, default)

    def files(self) -> list[str]:
        """Return all spec files for the parser."""
        return [
            name.format(dir=self.dir)
            for value in self.values()
            if (name := value.get("file", self.file)) is not None
        ]

    def command(self) -> str:
        """Return the parser command."""
        commands = [f"cat {' _ '.join(self.files())}"]
        for value in self.values():
            if (command := value.get("command", None)):
                commands.append(f"printf '{self.separator}'")
                commands.append(command)
        return " && ".join(commands)

    def convert(self, key: str, values: list[str]) -> Any:
        """Convert output values for one parser spec."""
        func = self.specs[key].get("func", self.func)
        return func(values)

    async def get_data(self) -> dict[str, list[str]]:
        """Run the command and parse the output into a data dictionary."""
        keys = list(self.specs.keys())
        command = self.command()
        async with self.session.get(command) as output:
            outputs = output.strip(self.boundary).split(self.separator)
            groups = {keys[i]: o.splitlines() for i, o in enumerate(outputs)}
            data = {
                key: self.convert(key, values)
                for key, values in groups.items()
                if self.get(key, {}).get("capture", True)
            }
            for nested in [
                data.pop(key)
                for key in keys
                if self.get(key, {}).get("unwrap", False)
                and isinstance(data[key], dict)  # Flatten (unwrap) only dicts
            ]:
                data.update(nested)
            return data
    

class MPowerBoardParser(MPowerDataParser):
    """mFi mPower parser for board information."""

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
        """Extract static board information."""
        data = {
            match.group(1): match.group(2)
            for value in values
            if (match := re.match(r"^board.(\w+)=(.*)", value))
        }
        data["ports"] = int(self.PORTS.get(data["sysid"].lower(), 0))
        hwaddr = data.pop("hwaddr")
        data["hwaddr"] = ':'.join(hwaddr[i:i+2] for i in range(0, 12, 2))
        return data

    def func_ifconfig(self, values: list[str]) -> dict[str, str]:
        """Extract hardware addresses from ifconfig output."""
        data = {
            "hwaddrs": {
                MPowerNetwork.from_dev(match.group(1)).name.lower(): match.group(2)
                for value in values
                if (match := re.match(r"^([a-zA-Z0-9]+).*?HWaddr ([0-9A-Fa-f:]{17})", value))
            }
        }
        return data
    
    @property
    def specs(self) -> dict[str, dict[str, Any]]:
        """Return the parser specs."""
        return {
            "info": {"file": "/etc/board.info", "func": self.func_info, "unwrap": True},
            "ifconfig": {"command": "ifconfig -a", "func": self.func_ifconfig, "unwrap": True},
            "separator": {"command": f"printf '{self.separator}' > _", "capture": False},
        }
    

class MPowerStatusParser(MPowerDataParser):
    """mFi mPower parser for status information."""

    def func(self, values: list[str]) -> str:
        """Unwrap value."""
        return values[0]

    def func_led_status(self, values: list[str]) -> MPowerLED:
        """Unwrap value and convert to LED status enum type."""
        status = self.cast(values[0].split()[0], int)
        return None if status is None else MPowerLED(status)
    
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
        data["iface"] = MPowerNetwork.from_dev(data["iface"])
        return data
    
    @property
    def specs(self) -> dict[str, dict[str, Any]]:
        """Return the parser specs."""
        return {
            "firmware_version": {"file": "/usr/etc/.version"},
            "firmware_build": {"file": "/usr/etc/.build",},
            "led": {"file": "/proc/led/status", "func": self.func_led_status},
            "hostname": {"file": "/proc/sys/kernel/hostname"},
            "ip_route": {"command": "ip route", "func": self.func_ip_route, "unwrap": True},
        }
    

class MPowerPortDataParser(MPowerDataParser):
    """mFi mPower parser base for port data."""

    _ports: int

    def __init__(
        self,
        session: MPowerSession,
        ports: int,
    ) -> None:
        """Initialize the port parser."""
        super().__init__(session)
        self._ports = ports

    @property
    def ports(self) -> int:
        """Return the number of ports."""
        return self._ports


class MPowerPortConfigParser(MPowerPortDataParser):
    """mFi mPower parser for port config."""

    @property
    def dir(self) -> str:
        """Return the default directory for port config data."""
        return "/etc/persistent/cfg"

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
    def specs(self) -> dict[str, dict[str, Any]]:
        """Return the parser specs."""
        return {
            "label": {"file": "{dir}/config_file", "func": self.func_label},
            "vpower": {"file": "{dir}/vpower_cfg", "func": self.func_vpower, "unwrap": True},
        }
    

class MPowerPortSensorsParser(MPowerPortDataParser):
    """mFi mPower parser for port sensors."""

    @property
    def dir(self) -> str:
        """Return the default directory for port sensor data."""
        return "/proc/power"

    def func_float(self, values: list[str]) -> list[float | None]:
        """Convert float readings."""
        return [self.cast(value, float) for value in values]

    def func_bool(self, values: list[str]) -> list[bool | None]:
        """Convert boolean readings."""
        return [self.cast(self.cast(value, int), bool) for value in values]
    
    @property
    def specs(self) -> dict[str, dict[str, Any]]:
        """Return the parser specs."""
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