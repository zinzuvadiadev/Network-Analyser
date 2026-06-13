from __future__ import annotations
import platform
from .base import PlatformBackend


def get_platform_backend() -> PlatformBackend:
    system = platform.system()
    if system == "Linux":
        from .linux_backend import LinuxBackend
        return LinuxBackend()
    elif system == "Windows":
        from .windows_backend import WindowsBackend
        return WindowsBackend()
    else:
        raise RuntimeError(f"Unsupported platform: {system}. Only Linux and Windows are supported.")
