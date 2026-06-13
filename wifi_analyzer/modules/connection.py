from __future__ import annotations
from rich.panel import Panel
from ..platform_layer.base import PlatformBackend
from ..ui.tables import connection_table
from ..ui.banner import console


class ConnectionAnalyzer:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    def analyze(self):
        console.print("[bold cyan]Analyzing current connection...[/bold cyan]")
        info = self.backend.get_connection_info(self.interface)
        if info is None:
            console.print("[red]Not connected to any WiFi network.[/red]")
            return None
        # Supplement driver info from adapter capabilities if not in connection info
        if info.driver == "Unknown":
            caps = self.backend.get_adapter_capabilities(self.interface)
            info.driver = caps.get("driver", "Unknown")
            info.driver_version = caps.get("driver_version", "Unknown")
            info.vendor = caps.get("vendor", "Unknown")
        table = connection_table(info)
        console.print(table)
        return info
