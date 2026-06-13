from __future__ import annotations
from collections import defaultdict
from rich.table import Table
from rich.text import Text
from rich import box
from ..models import AccessPoint
from ..platform_layer.base import PlatformBackend
from ..ui.banner import console
from ..utils import overlapping_channels_24


class ChannelAnalyzer:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    def analyze(self) -> dict:
        console.print("[bold cyan]Scanning and analyzing channel congestion...[/bold cyan]")
        aps = self.backend.scan_networks(self.interface)
        if not aps:
            console.print("[yellow]No networks found.[/yellow]")
            return {}

        report = self._build_report(aps)
        self._display(report, aps)
        return report

    def _build_report(self, aps: list[AccessPoint]) -> dict:
        # Separate by band
        aps_24 = [a for a in aps if a.band == "2.4GHz"]
        aps_5 = [a for a in aps if a.band == "5GHz"]
        aps_6 = [a for a in aps if a.band == "6GHz"]

        # 2.4GHz: compute per-channel interference score
        ch24_aps: dict[int, list[AccessPoint]] = defaultdict(list)
        for ap in aps_24:
            ch24_aps[ap.channel].append(ap)

        interference: dict[int, float] = {}
        for ch in range(1, 15):
            score = 0.0
            for overlap_ch in overlapping_channels_24(ch):
                if overlap_ch == ch:
                    # own channel counts double
                    for ap in ch24_aps.get(ch, []):
                        score += max(0, ap.signal_dbm + 100)  # normalize to 0-70
                else:
                    for ap in ch24_aps.get(overlap_ch, []):
                        score += max(0, ap.signal_dbm + 100) * 0.5
            interference[ch] = score

        # Best 2.4GHz channel from non-overlapping set
        best_24 = min([1, 6, 11], key=lambda c: interference.get(c, 0))

        # 5GHz: simple occupancy count per channel
        ch5_aps: dict[int, list[AccessPoint]] = defaultdict(list)
        for ap in aps_5:
            ch5_aps[ap.channel].append(ap)

        best_5_ch = None
        if ch5_aps:
            best_5_ch = min(ch5_aps.keys(), key=lambda c: len(ch5_aps[c]))

        return {
            "aps_24": aps_24,
            "aps_5": aps_5,
            "aps_6": aps_6,
            "interference_24": interference,
            "ch24_aps": dict(ch24_aps),
            "ch5_aps": dict(ch5_aps),
            "best_24": best_24,
            "best_5": best_5_ch,
        }

    def _display(self, report: dict, aps: list[AccessPoint]):
        connected = next((a for a in aps if a.is_connected), None)
        current_ch = connected.channel if connected else None

        # 2.4GHz table
        if report["aps_24"]:
            console.print("\n[bold]2.4 GHz Channels[/bold]")
            table = Table(box=box.SIMPLE, header_style="bold cyan")
            table.add_column("Channel", width=9)
            table.add_column("APs", width=5)
            table.add_column("Interference Score", width=20)
            table.add_column("Status", width=20)

            for ch in range(1, 14):
                count = len(report["ch24_aps"].get(ch, []))
                score = report["interference_24"].get(ch, 0)
                is_current = current_ch == ch
                is_best = ch == report["best_24"]

                if count == 0 and score == 0:
                    continue

                bar_len = min(18, int(score / 5))
                bar = "█" * bar_len + "░" * (18 - bar_len)
                bar_color = "red" if score > 100 else ("yellow" if score > 40 else "green")

                status = ""
                if is_current:
                    status += "← you  "
                if is_best:
                    status += "★ recommended"

                table.add_row(
                    Text(f"  {ch}" + (" ★" if is_best else ""),
                         style="bold green" if is_best else ("bold cyan" if is_current else "")),
                    str(count) if count else "—",
                    Text(bar, style=bar_color),
                    Text(status, style="bold" if status else "dim"),
                )
            console.print(table)
            console.print(f"[dim]Recommended 2.4GHz channel: [bold]{report['best_24']}[/bold][/dim]")

        # 5GHz table
        if report["aps_5"]:
            console.print("\n[bold]5 GHz Channels[/bold]")
            table5 = Table(box=box.SIMPLE, header_style="bold cyan")
            table5.add_column("Channel", width=9)
            table5.add_column("APs", width=5)
            table5.add_column("Status", width=20)
            for ch, ap_list in sorted(report["ch5_aps"].items()):
                is_current = current_ch == ch
                is_best = ch == report["best_5"]
                table5.add_row(
                    Text(f"  {ch}" + (" ★" if is_best else ""),
                         style="bold green" if is_best else ("bold cyan" if is_current else "")),
                    str(len(ap_list)),
                    Text(("← you  " if is_current else "") + ("★ recommended" if is_best else ""),
                         style="bold" if (is_current or is_best) else "dim"),
                )
            console.print(table5)
            if report["best_5"]:
                console.print(f"[dim]Recommended 5GHz channel: [bold]{report['best_5']}[/bold][/dim]")
