from __future__ import annotations
import re
from typing import Optional

from .base import PlatformBackend
from ..models import AccessPoint, ConnectionInfo
from ..utils import run_cmd, freq_to_band


class WindowsBackend(PlatformBackend):

    def __init__(self):
        self.capabilities = {
            "has_iw": False,
            "has_nmcli": False,
            "can_set_power_mgmt": True,
            "supports_rescan": True,
        }

    def get_wifi_interfaces(self) -> list[str]:
        stdout, _, _ = run_cmd(["netsh", "wlan", "show", "interfaces"])
        names = re.findall(r"^\s+Name\s*:\s*(.+)$", stdout, re.MULTILINE)
        return [n.strip() for n in names]

    def scan_networks(self, interface: str) -> list[AccessPoint]:
        stdout, _, rc = run_cmd(
            ["netsh", "wlan", "show", "networks", "mode=bssid"], timeout=20
        )
        if rc != 0:
            return []

        aps: list[AccessPoint] = []
        # Split into per-AP blocks by "SSID N :" lines
        blocks = re.split(r"\nSSID \d+ *:", "\n" + stdout)
        for block in blocks[1:]:
            lines = block.strip().splitlines()
            if not lines:
                continue
            ssid = lines[0].strip()

            def _field(name: str) -> Optional[str]:
                m = re.search(rf"^\s*{re.escape(name)}\s*:\s*(.+)$", block, re.MULTILINE)
                return m.group(1).strip() if m else None

            # Each BSSID sub-block
            bssid_blocks = re.split(r"\n\s*BSSID \d+ *:", block)
            for bi, bb in enumerate(bssid_blocks[1:], 1):
                def _bfield(name: str) -> Optional[str]:
                    m = re.search(rf"^\s*{re.escape(name)}\s*:\s*(.+)$", bb, re.MULTILINE)
                    return m.group(1).strip() if m else None

                bssid = _bfield("BSSID " + str(bi)) or _bfield("BSSID") or "Unknown"
                # Simpler: first line of bb is the BSSID value
                bssid_line = bb.strip().splitlines()[0].strip() if bb.strip() else "Unknown"
                bssid = bssid_line if re.match(r"[\dA-Fa-f:]{17}", bssid_line) else "Unknown"

                signal_str = _bfield("Signal") or "0%"
                signal_pct = int(re.sub(r"[^0-9]", "", signal_str) or "0")
                signal_dbm = (signal_pct // 2) - 100

                channel_str = _bfield("Channel") or "0"
                try:
                    channel = int(channel_str)
                except ValueError:
                    channel = 0

                freq_mhz = 2407 + channel * 5 if channel <= 14 else 5000 + channel * 5
                band = freq_to_band(freq_mhz)

                rate_str = _bfield("Basic rates (Mbps)") or _bfield("Other rates") or "0"
                try:
                    rate_mbps = max(int(r) for r in re.findall(r"\d+", rate_str))
                except ValueError:
                    rate_mbps = 0

                security = _field("Authentication") or "Unknown"

                aps.append(AccessPoint(
                    ssid=ssid,
                    bssid=bssid,
                    channel=channel,
                    frequency_mhz=freq_mhz,
                    band=band,
                    signal_dbm=signal_dbm,
                    max_rate_mbps=rate_mbps,
                    security=security,
                    is_connected=False,
                    channel_width=None,
                ))

        aps.sort(key=lambda a: a.signal_dbm, reverse=True)
        return aps

    def get_connection_info(self, interface: str) -> Optional[ConnectionInfo]:
        stdout, _, rc = run_cmd(["netsh", "wlan", "show", "interfaces"])
        if rc != 0:
            return None

        def _field(name: str) -> Optional[str]:
            m = re.search(rf"^\s*{re.escape(name)}\s*:\s*(.+)$", stdout, re.MULTILINE)
            return m.group(1).strip() if m else None

        ssid = _field("SSID")
        if not ssid:
            return None
        bssid = _field("BSSID") or "Unknown"
        signal_str = _field("Signal") or "0%"
        signal_pct = int(re.sub(r"[^0-9]", "", signal_str) or "0")
        signal_dbm = (signal_pct // 2) - 100
        rate_str = _field("Receive rate (Mbps)") or "0"
        tx_rate_str = _field("Transmit rate (Mbps)") or "0"
        try:
            rx_rate = int(float(rate_str))
            tx_rate = int(float(tx_rate_str))
        except ValueError:
            rx_rate, tx_rate = 0, 0
        channel_str = _field("Channel") or "0"
        try:
            channel = int(channel_str)
        except ValueError:
            channel = 0
        freq_mhz = 2407 + channel * 5 if channel <= 14 else 5000 + channel * 5
        band = freq_to_band(freq_mhz)

        return ConnectionInfo(
            ssid=ssid,
            bssid=bssid,
            interface=interface,
            band=band,
            channel=channel,
            frequency_mhz=freq_mhz,
            signal_dbm=signal_dbm,
            tx_rate_mbps=tx_rate,
            rx_rate_mbps=rx_rate,
            tx_power_dbm=0,
            power_management=False,
            channel_width=None,
            mcs_index=None,
            driver="Unknown",
            driver_version="Unknown",
            vendor="Unknown",
            retry_excessive=0,
        )

    def get_signal_now(self, interface: str) -> int:
        stdout, _, _ = run_cmd(["netsh", "wlan", "show", "interfaces"])
        m = re.search(r"Signal\s*:\s*(\d+)%", stdout)
        if m:
            pct = int(m.group(1))
            return (pct // 2) - 100
        return -100

    def get_power_management_state(self, interface: str) -> bool:
        # Windows: assume power saving is active unless explicitly checked
        stdout, _, _ = run_cmd(["powercfg", "/query"])
        return "Power Saving" in stdout

    def set_power_management(self, interface: str, enabled: bool) -> bool:
        # 0 = max performance, 3 = max saving
        index = "3" if enabled else "0"
        _, _, rc = run_cmd(["powercfg", "-change", "-wireless-adapter-setting-index", index])
        return rc == 0

    def get_adapter_capabilities(self, interface: str) -> dict:
        stdout, _, _ = run_cmd(["netsh", "wlan", "show", "drivers"])
        caps: dict = {
            "driver": "Unknown",
            "driver_version": "Unknown",
            "vendor": "Unknown",
            "firmware": "Unknown",
            "supported_bands": [],
            "mimo_streams": None,
            "wifi_standard": "Unknown",
        }

        m = re.search(r"Driver\s*:\s*(.+)", stdout)
        if m:
            caps["driver"] = m.group(1).strip()
        m = re.search(r"Version\s*:\s*(.+)", stdout)
        if m:
            caps["driver_version"] = m.group(1).strip()
        m = re.search(r"Vendor\s*:\s*(.+)", stdout)
        if m:
            caps["vendor"] = m.group(1).strip()

        radio_types = re.findall(r"Radio types supported\s*:\s*(.+)", stdout)
        if radio_types:
            types = radio_types[0].lower()
            if "802.11b" in types or "802.11g" in types or "802.11n" in types:
                caps["supported_bands"].append("2.4GHz")
            if "802.11a" in types or "802.11n" in types or "802.11ac" in types or "802.11ax" in types:
                caps["supported_bands"].append("5GHz")
            if "802.11ax" in types and "6" in types:
                caps["supported_bands"].append("6GHz")
            if "802.11ax" in types:
                caps["wifi_standard"] = "Wi-Fi 6/6E (802.11ax)"
            elif "802.11ac" in types:
                caps["wifi_standard"] = "Wi-Fi 5 (802.11ac)"
            elif "802.11n" in types:
                caps["wifi_standard"] = "Wi-Fi 4 (802.11n)"

        return caps
