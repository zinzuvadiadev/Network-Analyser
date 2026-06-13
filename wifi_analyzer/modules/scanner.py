from __future__ import annotations
from rich.console import Console
from rich.text import Text
from ..platform_layer.base import PlatformBackend
from ..ui.tables import ap_table
from ..ui.banner import console


class NetworkScanner:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    def scan(self, rescan: bool = True):
        console.print("[bold cyan]Scanning for nearby networks...[/bold cyan]")
        aps = self.backend.scan_networks(self.interface)
        if not aps:
            console.print("[yellow]No networks found. Ensure WiFi is enabled.[/yellow]")
            return []
        table = ap_table(aps)
        console.print(table)
        console.print(f"\n[dim]Found {len(aps)} network(s). ★ = currently connected[/dim]")
        return aps
