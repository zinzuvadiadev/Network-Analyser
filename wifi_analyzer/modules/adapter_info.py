from __future__ import annotations
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box
from ..platform_layer.base import PlatformBackend
from ..ui.banner import console


class AdapterInfo:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    def display(self):
        console.print("[bold cyan]Gathering adapter capabilities...[/bold cyan]")
        caps = self.backend.get_adapter_capabilities(self.interface)
        conn = self.backend.get_connection_info(self.interface)
        current_band = conn.band if conn else None

        table = Table(box=box.ROUNDED, header_style="bold cyan", show_header=False,
                      min_width=55)
        table.add_column("Field", style="bold", width=22)
        table.add_column("Value")

        bands = caps.get("supported_bands", [])
        streams = caps.get("mimo_streams")

        band_text = Text()
        for b in bands:
            if b == current_band:
                band_text.append(f"{b} ← connected  ", style="bold green")
            else:
                band_text.append(f"{b}  ", style="dim")

        streams_str = f"{streams}×{streams} MIMO" if streams else "Unknown"
        warn_band = (current_band == "2.4GHz" and "5GHz" in bands)

        rows = [
            ("Interface", self.interface),
            ("Driver", caps.get("driver", "Unknown")),
            ("Driver Version", caps.get("driver_version", "Unknown")),
            ("Vendor", caps.get("vendor", "Unknown")),
            ("Firmware", caps.get("firmware", "Unknown")),
            ("WiFi Standard", caps.get("wifi_standard", "Unknown")),
            ("Supported Bands", band_text),
            ("MIMO Streams", streams_str),
        ]

        for field, value in rows:
            if isinstance(value, str):
                table.add_row(field, value)
            else:
                table.add_row(field, value)

        console.print(Panel(table, title="[bold]WiFi Adapter Capabilities[/bold]",
                            border_style="cyan"))

        if warn_band:
            console.print(
                "[bold yellow]⚠ Your adapter supports 5GHz but you are connected to 2.4GHz.\n"
                "  Connect to your 5GHz SSID for significantly better performance.[/bold yellow]"
            )

        return caps
