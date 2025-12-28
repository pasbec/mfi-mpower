"""Ubiquiti mFi MPower exceptions"""

from __future__ import annotations


class MPowerError(Exception):
    """General mFi MPower error."""


class MPowerDataError(MPowerError):
    """Error related to data validity and parsing."""


class MPowerConnectionError(MPowerError):
    """Error related to connections."""


class MPowerAuthenticationError(MPowerError):
    """Error related to authentication."""


class MPowerCommandError(MPowerError):
    """Error related to command execution."""
