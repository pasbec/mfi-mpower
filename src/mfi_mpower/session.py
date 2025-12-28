"""Ubiquiti mFi MPower SSH session"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import asyncssh

from .exceptions import (
    MPowerAuthenticationError,
    MPowerConnectionError,
    MPowerDataError,
    MPowerCommandError,
)


class MPowerSession:
    """mFi mPower session representation."""

    _host: str
    _username: str
    _password: str
    _conn: asyncssh.SSHClientConnection | None
    _lock: asyncio.Lock

    # NOTE: Ubiquiti mFi mPower Devices with firmware 2.1.11 use Dropbear SSH 0.51 (27 Mar 2008).
    options: dict = {
        "kex_algs": "diffie-hellman-group1-sha1",
        "encryption_algs": "aes128-cbc",
        # https://github.com/ronf/asyncssh/issues/263
        "server_host_key_algs": "ssh-rsa",
        # https://github.com/ronf/asyncssh/issues/132
        "known_hosts": None,
    }

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
    ) -> None:
        """Initialize the session."""
        self._host = host
        self._username = username
        self._password = password
        self._conn = None
        self._lock = asyncio.Lock()

    @property
    def host(self) -> str:
        """Return the host."""
        return self._host

    async def connect(self) -> None:
        """Establish SSH connection."""
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
        try:
            self._conn = await asyncssh.connect(
                host=self._host,
                username=self._username,
                password=self._password,
                **self.options,
            )
        except asyncssh.PermissionDenied as exc:
            raise MPowerAuthenticationError(
                f"Login to device {self.host} failed due to wrong SSH credentials"
            ) from exc
        except (OSError, asyncssh.Error) as exc:
            info = f"{type(exc).__name__}({exc})"
            raise MPowerConnectionError(
                f"Connection to device {self.host} failed: {info}"
            ) from exc

    async def close(self) -> None:
        """Close SSH connection."""
        if self._conn:
            self._conn.close()
            await self._conn.wait_closed()
            self._conn = None

    @property
    async def connection(self) -> asyncssh.SSHClientConnection:
        """Return active SSH connection, establishing it if necessary."""
        async with self._lock:
            if self._conn is None or self._conn.is_closed():
                await self.connect()
            return self._conn

    async def run(self, command: str) -> str:
        """Run command over SSH."""
        connection = await self.connection
        process = await connection.run(command)
        status = process.exit_status
        if status != 0:
            raise MPowerCommandError(
                f"Command '{command}' on device {self.host} failed with exit code {status}"
            )
        return process.stdout
    
    @asynccontextmanager
    async def get(self, command) -> AsyncGenerator[str, None]:
        """Run command over SSH and yield output in context manager."""
        try:
            output = await self.run(command)
            yield output
        except Exception as exc:
            info = f"{type(exc).__name__}({exc})"
            raise MPowerDataError(
                f"Data processing for '{command}' on device {self.host} failed: {info}"
            ) from exc
