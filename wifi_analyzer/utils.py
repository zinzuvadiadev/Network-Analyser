from __future__ import annotations
import os
import platform
import subprocess
import statistics
from typing import Optional


class CommandError(Exception):
    pass


def run_cmd(args: list[str], timeout: int = 15) -> tuple[str, str, int]:
    """Run a command, return (stdout, stderr, returncode). Never raises."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "timeout", 1
    except FileNotFoundError:
        return "", f"command not found: {args[0]}", 127
    except Exception as e:
        return "", str(e), 1


def run_cmd_sudo(args: list[str], timeout: int = 15) -> tuple[str, str, int]:
    if platform.system() == "Linux":
        return run_cmd(["sudo"] + args, timeout=timeout)
    return run_cmd(args, timeout=timeout)


def check_root() -> bool:
    if platform.system() == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return os.getuid() == 0


def dbm_to_quality(dbm: int) -> str:
    if dbm >= -50:
        return "Excellent"
    if dbm >= -60:
        return "Good"
    if dbm >= -70:
        return "Fair"
    if dbm >= -80:
        return "Poor"
    return "Very Poor"


def dbm_to_bar(dbm: int, width: int = 10) -> str:
    """Return a Unicode block bar representing signal strength."""
    pct = max(0.0, min(1.0, (dbm + 100) / 60))  # -100=-0%, -40=+100%
    filled = round(pct * width)
    return "█" * filled + "░" * (width - filled)


def nmcli_pct_to_dbm(pct: int) -> int:
    """Convert nmcli 0-100 signal quality to approximate dBm."""
    return (pct // 2) - 100


def freq_to_band(freq_mhz: int) -> str:
    if 2400 <= freq_mhz <= 2500:
        return "2.4GHz"
    if 5150 <= freq_mhz <= 5925:
        return "5GHz"
    if 5925 <= freq_mhz <= 7125:
        return "6GHz"
    return "Unknown"


def channel_to_freq_24(channel: int) -> int:
    """2.4GHz channel to center frequency in MHz."""
    if channel == 14:
        return 2484
    return 2407 + channel * 5


def channel_to_freq_5(channel: int) -> int:
    """5GHz channel to center frequency in MHz."""
    return 5000 + channel * 5


def overlapping_channels_24(channel: int) -> list[int]:
    """Return list of 2.4GHz channels that overlap with the given channel."""
    return [c for c in range(1, 15) if abs(c - channel) < 5]


def median_signal(readings: list[int]) -> int:
    if not readings:
        return -100
    return int(statistics.median(readings))
