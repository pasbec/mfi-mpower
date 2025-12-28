"""Ubiquiti mFi MPower SSH interface"""

from __future__ import annotations

import json
from typing import Any

from .enums import MPowerLED
from .parsers import (
    MPowerBoardParser,
    MPowerPortDataParser,
    MPowerPortConfigParser,
    MPowerPortSensorsParser,
    MPowerStatusParser,
)
from .session import MPowerSession


class MPowerInterface:
    """mFi mPower interface representation."""

    _board: dict | None
    _session: MPowerSession

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the interface."""
        self._board = None
        self._session = MPowerSession(host, username, password)

    @property
    def session(self) -> MPowerSession:
        """Return the session."""
        return self._session

    @property
    def host(self) -> str:
        """Return the session host."""
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
            self._board = await MPowerBoardParser(self.session).get_data()
        return self._board

    async def get_status_info(self) -> dict:
        """Get device status information."""
        return await MPowerStatusParser(self.session).get_data()

    async def get_ports(self) -> int:
        """Get number of ports from board info."""
        return (await self.get_board())["ports"]

    async def get_port_data_from_parser(self, parser: MPowerPortDataParser) -> list[dict]:
        """Get port data from any port parser."""
        data = await parser.get_data()
        return [{k: v for k, v in zip(data, values)} for values in zip(*data.values())]

    async def get_port_config_data(self) -> list[dict]:
        """Get port config data."""
        ports = await self.get_ports()
        return await self.get_port_data_from_parser(MPowerPortConfigParser(self.session, ports))

    async def get_port_sensor_data(self) -> list[dict]:
        """Get port sensor data."""
        ports = await self.get_ports()
        return await self.get_port_data_from_parser(MPowerPortSensorsParser(self.session, ports))

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

    async def set_proc(self, proc: str, value: Any) -> None:
        """Set state via file."""
        await self.run(f"echo {value} > /proc/{proc}")

    async def set_led(self, led: MPowerLED) -> None:
        """Set LED state to the given LED value."""
        await self.set_proc("led/status", MPowerLED.OFF.value)
        await self.set_proc("led/status", led.value)

    async def set_port_lock(self, port: int, lock: bool) -> None:
        """Set port lock state to on/off."""
        await self.set_proc(f"power/lock{port}", int(lock))

    async def set_port_output(self, port: int, output: bool) -> None:
        """Set port output state to on/off."""
        await self.set_proc(f"power/output{port}", int(output))