from __future__ import annotations
import platform
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Confirm
from ..platform_layer.base import PlatformBackend
from ..ui.banner import console
from ..utils import check_root


class PowerManager:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    def check_and_display(self):
        pm_on = self.backend.get_power_management_state(self.interface)
        if pm_on:
            body = Text()
            body.append("Power Management is ", style="white")
            body.append("ON\n\n", style="bold red")
            body.append(
                "This causes your WiFi adapter to throttle its radio activity to save\n"
                "battery power. The result is erratic throughput and high latency spikes.\n"
                "This is a very common cause of laptops getting 4 Mb/s where phones get 40 Mb/s.\n\n",
                style="white"
            )
            body.append("Fix (Linux): ", style="bold")
            body.append(f"sudo iwconfig {self.interface} power off\n", style="bright_cyan")
            body.append("Fix (Windows): ", style="bold")
            body.append("Set adapter to 'Maximum Performance' in Device Manager", style="bright_cyan")
            console.print(Panel(body, title="[bold red]⚠ Power Management: ON — Throttling Active[/bold red]",
                                border_style="red"))
            self._offer_fix()
        else:
            body = Text()
            body.append("Power Management is ", style="white")
            body.append("OFF\n\n", style="bold green")
            body.append("Your adapter is running at full performance.", style="white")
            console.print(Panel(body, title="[bold green]✓ Power Management: OFF — Good[/bold green]",
                                border_style="green"))
        return pm_on

    def _offer_fix(self):
        if platform.system() != "Linux":
            return
        if not Confirm.ask("\n[bold]Apply fix now?[/bold] (disables power management)"):
            return

        console.print(f"[cyan]Running: sudo iwconfig {self.interface} power off[/cyan]")
        success = self.backend.set_power_management(self.interface, enabled=False)

        if success:
            console.print("[green]✓ Power management disabled. Re-run monitor to verify improvement.[/green]")
            if Confirm.ask("Make permanent across reboots? (writes a systemd service)"):
                if hasattr(self.backend, "make_pm_permanent"):
                    ok = self.backend.make_pm_permanent(self.interface)
                    if ok:
                        console.print("[green]✓ Systemd service installed. Will apply on every boot.[/green]")
                    else:
                        console.print("[red]Failed to install service. Try running with sudo.[/red]")
        else:
            console.print("[red]Fix failed. Try running the tool with sudo.[/red]")
