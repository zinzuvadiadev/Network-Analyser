from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AccessPoint:
    ssid: str
    bssid: str
    channel: int
    frequency_mhz: int
    band: str               # "2.4GHz" | "5GHz" | "6GHz"
    signal_dbm: int
    max_rate_mbps: int
    security: str
    is_connected: bool
    channel_width: Optional[str] = None  # None if iw unavailable


@dataclass
class ConnectionInfo:
    ssid: str
    bssid: str
    interface: str
    band: str
    channel: int
    frequency_mhz: int
    signal_dbm: int
    tx_rate_mbps: int
    rx_rate_mbps: Optional[int]
    tx_power_dbm: int
    power_management: bool      # True = throttling active
    channel_width: Optional[str]
    mcs_index: Optional[int]
    driver: str
    driver_version: str
    vendor: str
    retry_excessive: int        # high value = RF quality problem


@dataclass
class SpeedResult:
    download_mbps: float
    upload_mbps: float
    latency_ms: float
    jitter_ms: float
    server: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CoveragePoint:
    x: float            # meters from room origin
    y: float
    signal_dbm: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DiagnosticFinding:
    severity: str       # "critical" | "warning" | "info" | "ok"
    category: str       # "band" | "power_management" | "channel" | "signal" | "driver"
    title: str
    detail: str
    recommendation: str
