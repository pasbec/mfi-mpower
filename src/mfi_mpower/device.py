"""Ubiquiti mFi MPower device"""
from __future__ import annotations

import json
from random import randrange
import ssl
import time

import aiohttp
import asyncio
from yarl import URL

from .board import MPowerBoard
from .entities import MPowerSensor, MPowerSwitch
from .exceptions import (
    MPowerAPIError,
    MPowerAPIConnError,
    MPowerAPIAuthError,
    MPowerAPIReadError,
    MPowerAPIDataError,
)


class MPowerDevice:
    """mFi mPower device representation."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        use_ssl: bool = False,
        verify_ssl: bool = False,
        cache_time: float = 0.0,
        board_info: bool | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the device."""
        self.host = host
        self.url = URL(f"https://{host}" if use_ssl else f"http://{host}")
        self.username = username
        self.password = password
        self.cache_time = cache_time
        self._board_info = board_info

        self._board = MPowerBoard(self)

        if session is None:
            self._session_owned = True
            self._session = None
        else:
            self._session_owned = False
            self._session = session

        # NOTE: Ubiquiti mFi mPower Devices with firmware 2.1.11 use OpenSSL 1.0.0g (18 Jan 2012)
        if use_ssl:
            self._ssl = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
            self._ssl.set_ciphers("AES128-SHA:@SECLEVEL=0")
            self._ssl.verify_mode = ssl.CERT_REQUIRED if verify_ssl else ssl.CERT_NONE
            self._ssl.certs_loaded = False
        else:
            self._ssl = False

        self._cookie = (
            f"AIROS_SESSIONID={''.join([str(randrange(9)) for i in range(32)])}"
        )

        self._authenticated = False
        self._time = time.time()
        self._data = {}

    async def __aenter__(self) -> MPowerDevice:
        """Enter context manager scope."""
        await self.login()
        await self.update()
        return self

    async def __aexit__(self, *kwargs) -> None:
        """Leave context manager scope."""
        await self.logout()

    def __str__(self):
        """Represent this device as string."""
        if self._data:
            keys = ["name", "ipaddr", "hwaddr", "model"]
        else:
            keys = ["host"]
        vals = ", ".join([f"{k}={getattr(self, k)}" for k in keys])
        return f"{__class__.__name__}({vals})"

    @property
    def name(self) -> str:
        """Return the device name."""
        if self.updated:
            try:
                return self.hostname
            except Exception:  # pylint: disable=broad-except
                pass
        return self.host

    @property
    def manufacturer(self) -> str:
        """Return the device manufacturer."""
        return "Ubiquiti"

    @property
    def board(self) -> MPowerBoard:
        """Return the device board."""
        return self._board

    @property
    def eu_model(self) -> bool | None:
        """Return whether this device is a EU model with type F sockets."""
        if self._board.updated:
            return self._board.eu_model
        return None

    async def request(
        self, method: str, url: str | URL, data: dict | None = None
    ) -> str:
        """Session wrapper for general requests."""
        url = URL(url)
        if not url.is_absolute():
            url = self.url / str(url).lstrip("/")
        try:
            async with self._session.request(
                method=method,
                url=url,
                headers={"Cookie": self._cookie},
                data=data,
                ssl=self._ssl,
                chunked=None,
            ) as resp:
                if resp.status != 200:
                    raise MPowerAPIReadError(
                        f"Received bad HTTP status code from device {self.name}: {resp.status}"
                    )

                # NOTE: Un-authorized request will redirect to /login.cgi
                if str(resp.url.path) == "/login.cgi":
                    self._authenticated = False
                else:
                    self._authenticated = True

                return await resp.text()
        except aiohttp.ClientSSLError as exc:
            raise MPowerAPIConnError(
                f"Could not verify SSL certificate of device {self.name}: {exc}"
            ) from exc
        except aiohttp.ClientError as exc:
            raise MPowerAPIConnError(
                f"Connection to device {self.name} failed: {exc}"
            ) from exc

    async def load_certs(self):
        if (self._ssl and self._ssl.verify_mode != ssl.CERT_NONE and not self._ssl.certs_loaded):
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._ssl.load_default_certs)
            self._ssl.certs_loaded = True

    async def login(self) -> None:
        """Login to this device."""
        if self._session_owned and self._session is None:
            self._session = aiohttp.ClientSession()
        if not self._authenticated:
            await self.load_certs()
            await self.request(
                "POST",
                "/login.cgi",
                data={"username": self.username, "password": self.password},
            )

            if not self._authenticated:
                raise MPowerAPIAuthError(
                    f"Login to device {self.name} failed due to wrong API credentials"
                )

    async def logout(self) -> None:
        """Logout from this device."""
        if self._authenticated:
            await self.request("POST", "/logout.cgi")
        if self._session_owned:
            await self._session.close()
            self._session = None

    async def update(self) -> None:
        """Update sensor data."""
        # NOTE: If board_info is
        #        - True, one attempt will be made (raise)
        #        - None, one attempt will be made (no raise)
        #        - False, no attempt will be made
        #       to update the board data!
        if not self._board.updated and self._board_info is not False:
            try:
                self._board = MPowerBoard(self)
                await self._board.update()
            except Exception as exc:  # pylint: disable=broad-except
                if self._board_info:
                    raise exc

        if not self._data or (time.time() - self._time) > self.cache_time:
            await self.login()
            text_status = await self.request("GET", "/status.cgi")
            text_sensors = await self.request("GET", "/mfi/sensors.cgi")

            try:
                data = json.loads(text_status)
                data.update(json.loads(text_sensors))
            except aiohttp.ContentTypeError as exc:
                raise MPowerAPIDataError(
                    f"Received invalid data from device {self.name}: {exc}"
                ) from exc

            status = data.get("status", None)
            if status != "success":
                raise MPowerAPIDataError(
                    f"Received invalid sensor update status from device {self.name}: {status}"
                )

            self._time = time.time()
            self._data = data

    @property
    def updated(self) -> bool:
        """Return if the device data has already been updated."""
        return bool(self._data)

    @property
    def data(self) -> dict:
        """Return device data."""
        if not self._data:
            raise MPowerAPIError(
                f"Device data for device {self.name} must be updated first"
            )
        return self._data

    @data.setter
    def data(self, data: dict) -> None:
        """Set device data."""
        self._data = data

    @property
    def host_data(self) -> dict:
        """Return the device host data."""
        return self.data.get("host", {})

    @property
    def fwversion(self) -> str:
        """Return the device host firmware version."""
        return self.host_data.get("fwversion", "")

    @property
    def hostname(self) -> str:
        """Return the device host name."""
        return self.host_data.get("hostname", "")

    @property
    def lan_data(self) -> dict:
        """Return the device LAN data."""
        return self.data.get("lan", {})

    @property
    def wlan_data(self) -> dict:
        """Return the device WLAN data."""
        return self.data.get("wlan", {})

    @property
    def ipaddr(self) -> str:
        """Return the device IP address from LAN if connected, else from WLAN."""
        lan_connected = self.lan_data.get("status", "") != "Unplugged"
        if lan_connected:
            return self.lan_data.get("ip", "")
        return self.wlan_data.get("ip", "")

    @property
    def hwaddr(self) -> str:
        """Return the device hardware address from LAN if connected, else from WLAN."""
        lan_connected = self.lan_data.get("status", "") != "Unplugged"
        if lan_connected:
            return self.lan_data.get("hwaddr", "")
        return self.wlan_data.get("hwaddr", "")

    @property
    def unique_id(self) -> str:
        """Return a unique device id from combined LAN/WLAN hardware addresses."""
        lan_hwaddr = self.lan_data.get("hwaddr", "")
        wlan_hwaddr = self.wlan_data.get("hwaddr", "")
        if lan_hwaddr and wlan_hwaddr:
            return f"{lan_hwaddr}-{wlan_hwaddr}"
        return ""

    @property
    def port_data(self) -> list[dict]:
        """Return the device port data."""
        return self.data.get("sensors", [])

    @property
    def ports(self) -> int:
        """Return the number of available device ports."""
        return len(self.port_data)

    @property
    def model(self) -> str:
        """Return the model name of this device as string."""
        if self._board.updated:
            return self._board.model
        ports = self.ports
        prefix = "mPower"
        suffix = " (EU)" if self.eu_model else ""
        if ports == 1:
            return f"{prefix} mini" + suffix
        if ports == 3:
            return prefix + suffix
        if ports in [6, 8]:
            return f"{prefix} Pro" + suffix
        return "Unknown"

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
