from __future__ import annotations
import re
import shutil
import time
from typing import Optional

from .base import PlatformBackend
from ..models import AccessPoint, ConnectionInfo
from ..utils import run_cmd, run_cmd_sudo, freq_to_band, nmcli_pct_to_dbm


def _decode_nmcli_ssid(ssid: str) -> str:
    """Decode nmcli's \\xNN hex escape sequences (e.g. curly quotes) to proper Unicode."""
    def replace_seq(m: re.Match) -> str:
        hex_bytes = bytes(int(h, 16) for h in re.findall(r"[0-9a-fA-F]{2}", m.group(0).replace("\\x", "")))
        try:
            return hex_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return m.group(0)
    return re.sub(r"(?:\\x[0-9a-fA-F]{2})+", replace_seq, ssid)


class LinuxBackend(PlatformBackend):

    def __init__(self):
        self.capabilities = {
            "has_iw": shutil.which("iw") is not None,
            "has_nmcli": shutil.which("nmcli") is not None,
            "has_iwconfig": shutil.which("iwconfig") is not None,
            "can_set_power_mgmt": True,   # requires sudo at runtime
            "supports_rescan": True,
        }

    # ------------------------------------------------------------------ #
    # Interface discovery                                                  #
    # ------------------------------------------------------------------ #

    def get_wifi_interfaces(self) -> list[str]:
        stdout, _, _ = run_cmd(["ip", "link", "show"])
        ifaces = [i.rstrip(":") for i in re.findall(r"^\d+:\s+(wl\S+)", stdout, re.MULTILINE)]
        # prefer the connected one first
        connected = self._get_connected_interface()
        if connected and connected in ifaces:
            ifaces = [connected] + [i for i in ifaces if i != connected]
        return ifaces

    def _get_connected_interface(self) -> Optional[str]:
        if not self.capabilities["has_nmcli"]:
            return None
        stdout, _, rc = run_cmd(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device"])
        if rc != 0:
            return None
        for line in stdout.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[1] == "wifi" and parts[2] == "connected":
                return parts[0]
        return None

    # ------------------------------------------------------------------ #
    # Network scan                                                         #
    # ------------------------------------------------------------------ #

    def scan_networks(self, interface: str) -> list[AccessPoint]:
        if self.capabilities["has_nmcli"]:
            return self._scan_nmcli(interface)
        return []

    def _scan_nmcli(self, interface: str) -> list[AccessPoint]:
        fields = "SSID,BSSID,CHAN,FREQ,SIGNAL,SECURITY,RATE,ACTIVE"
        stdout, _, rc = run_cmd(
            ["nmcli", "--mode", "tabular", "--terse",
             "--fields", fields,
             "device", "wifi", "list", "--rescan", "yes"],
            timeout=30,
        )
        if rc != 0 or not stdout.strip():
            # fall back without rescan
            stdout, _, _ = run_cmd(
                ["nmcli", "--mode", "tabular", "--terse",
                 "--fields", fields,
                 "device", "wifi", "list"],
                timeout=15,
            )

        aps: list[AccessPoint] = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            # nmcli escapes colons in BSSIDs as \: — replace before splitting
            # Strategy: replace \: with a placeholder, split on :, restore
            safe = line.replace("\\:", "\x00")
            parts = safe.split(":")
            parts = [p.replace("\x00", ":") for p in parts]

            if len(parts) < 8:
                continue

            ssid, bssid, chan, freq_str, signal_str, security, rate_str, active = (
                parts[0], parts[1], parts[2], parts[3],
                parts[4], parts[5], parts[6], parts[7],
            )

            try:
                channel = int(chan) if chan.strip() else 0
            except ValueError:
                channel = 0

            try:
                freq_mhz = int(re.sub(r"[^0-9]", "", freq_str))
            except ValueError:
                freq_mhz = 0

            try:
                signal_pct = int(signal_str.strip())
                signal_dbm = nmcli_pct_to_dbm(signal_pct)
            except ValueError:
                signal_dbm = -100

            try:
                rate_mbps = int(re.sub(r"[^0-9]", "", rate_str.split()[0]))
            except (ValueError, IndexError):
                rate_mbps = 0

            band = freq_to_band(freq_mhz)
            is_connected = active.strip().lower() in ("yes", "*")

            aps.append(AccessPoint(
                ssid=_decode_nmcli_ssid(ssid.strip()) or "<hidden>",
                bssid=bssid.strip(),
                channel=channel,
                frequency_mhz=freq_mhz,
                band=band,
                signal_dbm=signal_dbm,
                max_rate_mbps=rate_mbps,
                security=security.strip() or "Open",
                is_connected=is_connected,
                channel_width=None,
            ))

        # Sort by signal strength descending
        aps.sort(key=lambda a: a.signal_dbm, reverse=True)
        return aps

    # ------------------------------------------------------------------ #
    # Current connection                                                   #
    # ------------------------------------------------------------------ #

    def get_connection_info(self, interface: str) -> Optional[ConnectionInfo]:
        iwconfig_info = self._parse_iwconfig(interface)
        nmcli_info = self._parse_nmcli_device(interface)
        iw_info = self._parse_iw_link(interface) if self.capabilities["has_iw"] else {}

        if not iwconfig_info.get("ssid") and not nmcli_info.get("ssid"):
            return None

        ssid = _decode_nmcli_ssid(iwconfig_info.get("ssid") or nmcli_info.get("ssid", "Unknown"))
        bssid = iwconfig_info.get("bssid") or nmcli_info.get("bssid", "Unknown")
        freq_mhz = nmcli_info.get("freq_mhz") or iw_info.get("freq_mhz") or 0
        channel = nmcli_info.get("channel") or iw_info.get("channel") or 0
        band = freq_to_band(freq_mhz) if freq_mhz else "Unknown"
        signal_dbm = iwconfig_info.get("signal_dbm", -100)
        tx_rate = iwconfig_info.get("tx_rate_mbps") or iw_info.get("tx_rate_mbps") or 0
        rx_rate = iw_info.get("rx_rate_mbps")
        tx_power = iwconfig_info.get("tx_power_dbm", 0)
        pm = iwconfig_info.get("power_management", False)
        retries = iwconfig_info.get("retry_excessive", 0)
        channel_width = iw_info.get("channel_width")
        mcs_index = iw_info.get("mcs_index")
        driver = nmcli_info.get("driver", "Unknown")
        driver_version = nmcli_info.get("driver_version", "Unknown")
        vendor = nmcli_info.get("vendor", "Unknown")

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
            tx_power_dbm=tx_power,
            power_management=pm,
            channel_width=channel_width,
            mcs_index=mcs_index,
            driver=driver,
            driver_version=driver_version,
            vendor=vendor,
            retry_excessive=retries,
        )

    def _parse_iwconfig(self, interface: str) -> dict:
        stdout, _, _ = run_cmd(["iwconfig", interface])
        info: dict = {}

        m = re.search(r'ESSID:"([^"]*)"', stdout)
        if m:
            info["ssid"] = m.group(1)

        m = re.search(r"Access Point:\s*([\dA-Fa-f:]+)", stdout)
        if m:
            info["bssid"] = m.group(1)

        m = re.search(r"Bit Rate[=:]\s*([\d.]+)\s*[MG]b/s", stdout)
        if m:
            rate = float(m.group(1))
            if "Gb" in stdout[m.start():m.end()+3]:
                rate *= 1000
            info["tx_rate_mbps"] = int(rate)

        m = re.search(r"Signal level[=:]\s*(-?\d+)\s*dBm", stdout)
        if m:
            info["signal_dbm"] = int(m.group(1))

        m = re.search(r"Tx-Power[=:]\s*(\d+)\s*dBm", stdout)
        if m:
            info["tx_power_dbm"] = int(m.group(1))

        m = re.search(r"Power Management:(\w+)", stdout)
        if m:
            info["power_management"] = m.group(1).lower() == "on"

        m = re.search(r"Tx excessive retries:(\d+)", stdout)
        if m:
            info["retry_excessive"] = int(m.group(1))

        return info

    def _parse_nmcli_device(self, interface: str) -> dict:
        stdout, _, _ = run_cmd(["nmcli", "-t", "device", "show", interface])
        info: dict = {}

        def _field(name: str) -> Optional[str]:
            m = re.search(rf"^{re.escape(name)}:(.*)", stdout, re.MULTILINE)
            return m.group(1).strip() if m else None

        info["ssid"] = _field("GENERAL.CONNECTION")
        info["driver"] = _field("GENERAL.DRIVER") or "Unknown"
        info["driver_version"] = _field("GENERAL.DRIVER-VERSION") or "Unknown"
        info["vendor"] = _field("GENERAL.VENDOR") or "Unknown"

        freq_str = _field("IP4.ADDRESS[1]")  # wrong field — use WIFI-PROPERTIES
        # Try to get frequency from active connection
        freq_raw = _field("GENERAL.METERED")  # placeholder — parse separately
        # Actually get frequency via nmcli device wifi
        stdout2, _, _ = run_cmd(
            ["nmcli", "-t", "-f", "ACTIVE,FREQ,CHAN,BSSID", "device", "wifi"]
        )
        for line in stdout2.splitlines():
            safe = line.replace("\\:", "\x00")
            parts = safe.split(":")
            parts = [p.replace("\x00", ":") for p in parts]
            if len(parts) >= 4 and parts[0].strip().lower() in ("yes", "*"):
                try:
                    freq_mhz = int(re.sub(r"[^0-9]", "", parts[1]))
                    info["freq_mhz"] = freq_mhz
                    info["channel"] = int(parts[2]) if parts[2].strip() else 0
                    info["bssid"] = parts[3].strip()
                except ValueError:
                    pass
                break

        return info

    def _parse_iw_link(self, interface: str) -> dict:
        stdout, _, rc = run_cmd(["iw", "dev", interface, "link"])
        if rc != 0:
            return {}
        info: dict = {}

        m = re.search(r"freq:\s*(\d+)", stdout)
        if m:
            info["freq_mhz"] = int(m.group(1))

        m = re.search(r"tx bitrate:\s*([\d.]+)\s*MBit/s(?:\s+MCS\s+(\d+))?(?:\s+(\d+)MHz)?", stdout)
        if m:
            info["tx_rate_mbps"] = int(float(m.group(1)))
            if m.group(2):
                info["mcs_index"] = int(m.group(2))
            if m.group(3):
                info["channel_width"] = f"{m.group(3)}MHz"

        m = re.search(r"rx bitrate:\s*([\d.]+)\s*MBit/s", stdout)
        if m:
            info["rx_rate_mbps"] = int(float(m.group(1)))

        return info

    # ------------------------------------------------------------------ #
    # Fast signal polling                                                  #
    # ------------------------------------------------------------------ #

    def get_signal_now(self, interface: str) -> int:
        """Read /proc/net/wireless directly — no subprocess overhead."""
        try:
            with open("/proc/net/wireless", "r") as f:
                for line in f:
                    if interface in line:
                        parts = line.split()
                        # Format: iface: status quality.link quality.level quality.noise
                        # level field is index 3 (0-based after iface:)
                        level = parts[3].rstrip(".")
                        val = int(float(level))
                        # /proc/net/wireless reports level as unsigned 8-bit or signed
                        if val > 0:
                            val -= 256   # convert unsigned to signed dBm
                        return val
        except Exception:
            pass
        # Fallback: iwconfig parse
        info = self._parse_iwconfig(interface)
        return info.get("signal_dbm", -100)

    # ------------------------------------------------------------------ #
    # Power management                                                     #
    # ------------------------------------------------------------------ #

    def get_power_management_state(self, interface: str) -> bool:
        info = self._parse_iwconfig(interface)
        return info.get("power_management", False)

    def set_power_management(self, interface: str, enabled: bool) -> bool:
        state = "on" if enabled else "off"
        _, _, rc = run_cmd_sudo(["iwconfig", interface, "power", state])
        return rc == 0

    def make_pm_permanent(self, interface: str) -> bool:
        """Write a systemd oneshot service to disable PM on boot."""
        service = f"""[Unit]
Description=Disable WiFi Power Management on {interface}
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/iwconfig {interface} power off
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
"""
        path = "/etc/systemd/system/wifi-pm-off.service"
        _, _, rc1 = run_cmd_sudo(
            ["bash", "-c", f"echo '{service}' > {path}"]
        )
        _, _, rc2 = run_cmd_sudo(["systemctl", "enable", "--now", "wifi-pm-off.service"])
        return rc1 == 0 and rc2 == 0

    # ------------------------------------------------------------------ #
    # Adapter capabilities                                                 #
    # ------------------------------------------------------------------ #

    def get_adapter_capabilities(self, interface: str) -> dict:
        caps: dict = {
            "driver": "Unknown",
            "driver_version": "Unknown",
            "vendor": "Unknown",
            "firmware": "Unknown",
            "supported_bands": [],
            "mimo_streams": None,
            "wifi_standard": "Unknown",
        }

        # Primary: sysfs driver symlink (most reliable, no sudo needed)
        import os
        driver_link = f"/sys/class/net/{interface}/device/driver"
        try:
            target = os.readlink(driver_link)
            caps["driver"] = os.path.basename(target)
        except OSError:
            pass

        # Driver version from sysfs
        try:
            ver_path = f"/sys/class/net/{interface}/device/driver/module/version"
            if os.path.exists(ver_path):
                with open(ver_path) as f:
                    caps["driver_version"] = f.read().strip()
        except OSError:
            pass

        # Vendor from sysfs
        try:
            vendor_path = f"/sys/class/net/{interface}/device/vendor"
            device_path = f"/sys/class/net/{interface}/device/device"
            if os.path.exists(vendor_path):
                with open(vendor_path) as f:
                    caps["vendor"] = f"PCI {f.read().strip()}"
        except OSError:
            pass

        # Fallback: nmcli for vendor/driver if sysfs didn't get it
        stdout, _, _ = run_cmd(["nmcli", "-t", "device", "show", interface])
        if caps["driver"] == "Unknown":
            m = re.search(r"^GENERAL\.DRIVER:(.*)", stdout, re.MULTILINE)
            if m:
                caps["driver"] = m.group(1).strip()
        if caps["driver_version"] == "Unknown":
            m = re.search(r"^GENERAL\.DRIVER-VERSION:(.*)", stdout, re.MULTILINE)
            if m:
                caps["driver_version"] = m.group(1).strip()
        m = re.search(r"^GENERAL\.VENDOR:(.*)", stdout, re.MULTILINE)
        if m and m.group(1).strip():
            caps["vendor"] = m.group(1).strip()
        m = re.search(r"^GENERAL\.FIRMWARE-VERSION:(.*)", stdout, re.MULTILINE)
        if m:
            caps["firmware"] = m.group(1).strip()

        # Infer band support and standard from driver name / scan results
        driver = caps["driver"].lower()
        known_chipsets = {
            "mt7925": {"bands": ["2.4GHz", "5GHz", "6GHz"], "streams": 2, "standard": "Wi-Fi 6E (802.11ax)"},
            "mt7921": {"bands": ["2.4GHz", "5GHz"], "streams": 2, "standard": "Wi-Fi 6 (802.11ax)"},
            "mt7615": {"bands": ["2.4GHz", "5GHz"], "streams": 4, "standard": "Wi-Fi 5 (802.11ac)"},
            "iwlwifi": {"bands": ["2.4GHz", "5GHz"], "streams": 2, "standard": "Wi-Fi 6 (802.11ax)"},
            "rtl8821": {"bands": ["2.4GHz", "5GHz"], "streams": 1, "standard": "Wi-Fi 5 (802.11ac)"},
            "ath9k": {"bands": ["2.4GHz", "5GHz"], "streams": 2, "standard": "Wi-Fi 4 (802.11n)"},
            "brcmfmac": {"bands": ["2.4GHz", "5GHz"], "streams": 2, "standard": "Wi-Fi 5 (802.11ac)"},
        }
        for key, info in known_chipsets.items():
            if key in driver:
                caps["supported_bands"] = info["bands"]
                caps["mimo_streams"] = info["streams"]
                caps["wifi_standard"] = info["standard"]
                break

        # modinfo for firmware info
        if caps["driver"] != "Unknown":
            stdout, _, _ = run_cmd(["modinfo", caps["driver"]])
            m = re.search(r"^firmware:(.*)", stdout, re.MULTILINE)
            if m:
                caps["firmware"] = m.group(1).strip()

        # iw phy fallback for bands
        if self.capabilities["has_iw"] and not caps["supported_bands"]:
            stdout, _, _ = run_cmd(["iw", "phy"])
            if "2412" in stdout or "2.4" in stdout:
                caps["supported_bands"].append("2.4GHz")
            if "5180" in stdout or "5 GHz" in stdout:
                caps["supported_bands"].append("5GHz")
            if "5955" in stdout or "6 GHz" in stdout:
                caps["supported_bands"].append("6GHz")

        return caps
