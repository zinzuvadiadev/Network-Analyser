from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from ..models import AccessPoint, ConnectionInfo


class PlatformBackend(ABC):
    """Abstract interface — all OS-specific code lives in subclasses."""

    capabilities: dict = {}

    @abstractmethod
    def get_wifi_interfaces(self) -> list[str]:
        """Return list of WiFi interface names."""

    @abstractmethod
    def scan_networks(self, interface: str) -> list[AccessPoint]:
        """Return list of nearby access points, sorted by signal (strongest first)."""

    @abstractmethod
    def get_connection_info(self, interface: str) -> Optional[ConnectionInfo]:
        """Return current connection details, or None if not connected."""

    @abstractmethod
    def get_signal_now(self, interface: str) -> int:
        """Return current signal in dBm. Fast — suitable for tight polling loops."""

    @abstractmethod
    def get_power_management_state(self, interface: str) -> bool:
        """Return True if power management is enabled (throttling may occur)."""

    @abstractmethod
    def set_power_management(self, interface: str, enabled: bool) -> bool:
        """Enable or disable power management. Returns True on success."""

    @abstractmethod
    def get_adapter_capabilities(self, interface: str) -> dict:
        """Return dict with keys: driver, driver_version, vendor, firmware,
        supported_bands (list), mimo_streams (int or None), wifi_standard (str)."""
