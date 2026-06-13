from __future__ import annotations
from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich import box
from ..models import AccessPoint, ConnectionInfo, DiagnosticFinding
from ..utils import dbm_to_quality, dbm_to_bar
from .banner import SEVERITY_COLORS, SEVERITY_ICONS, SIGNAL_COLORS, console


def _signal_markup(dbm: int) -> str:
    quality = dbm_to_quality(dbm)
    color = SIGNAL_COLORS.get(quality, "white")
    bar = dbm_to_bar(dbm, width=8)
    return f"[{color}]{dbm} dBm {bar}[/{color}]"


def ap_table(aps: list[AccessPoint]) -> Table:
    table = Table(
        title="Nearby WiFi Networks",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
        expand=True,
    )
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("SSID", min_width=14, no_wrap=True)
    table.add_column("BSSID", style="dim", width=18)
    table.add_column("Band", width=7)
    table.add_column("CH", width=4, justify="right")
    table.add_column("Width", width=6)
    table.add_column("Signal", min_width=22, no_wrap=True)
    table.add_column("Rate", width=9, justify="right")
    table.add_column("Security", width=13)

    for i, ap in enumerate(aps, 1):
        connected_marker = " ★" if ap.is_connected else ""
        ssid_markup = (f"[bold green]{ap.ssid}{connected_marker}[/bold green]"
                       if ap.is_connected else ap.ssid + connected_marker)
        band_color = ("bright_blue" if ap.band == "5GHz"
                      else ("bright_magenta" if ap.band == "6GHz" else "yellow"))

        table.add_row(
            str(i),
            ssid_markup,
            ap.bssid,
            f"[{band_color}]{ap.band}[/{band_color}]",
            str(ap.channel) if ap.channel else "—",
            ap.channel_width or "N/A",
            _signal_markup(ap.signal_dbm),
            f"{ap.max_rate_mbps} Mb/s" if ap.max_rate_mbps else "—",
            ap.security,
        )

    return table


def connection_table(info: ConnectionInfo) -> Table:
    table = Table(
        title=f"Current Connection — {info.ssid}",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_header=False,
        expand=False,
        min_width=60,
    )
    table.add_column("Field", style="bold", width=18)
    table.add_column("Value", min_width=38)

    quality = dbm_to_quality(info.signal_dbm)
    signal_color = SIGNAL_COLORS.get(quality, "white")
    pm_markup = ("[bold red]ON  ← throttling your speed![/bold red]"
                 if info.power_management else "[bold green]OFF  (good)[/bold green]")
    band_color = "bright_blue" if "5" in info.band else (
        "bright_magenta" if "6" in info.band else "yellow")
    retry_markup = (f"[red]{info.retry_excessive}[/red]"
                    if info.retry_excessive > 50 else str(info.retry_excessive))

    rows = [
        ("Interface", info.interface),
        ("SSID", info.ssid),
        ("BSSID", info.bssid),
        ("Band", f"[{band_color}]{info.band}[/{band_color}]"),
        ("Channel", str(info.channel) if info.channel else "N/A"),
        ("Frequency", f"{info.frequency_mhz} MHz" if info.frequency_mhz else "N/A"),
        ("Channel Width", info.channel_width or "N/A (install iw)"),
        ("MCS Index", str(info.mcs_index) if info.mcs_index is not None else "N/A"),
        ("Signal", f"[{signal_color}]{info.signal_dbm} dBm  {dbm_to_bar(info.signal_dbm, 8)}  {quality}[/{signal_color}]"),
        ("TX Rate", f"{info.tx_rate_mbps} Mb/s"),
        ("RX Rate", f"{info.rx_rate_mbps} Mb/s" if info.rx_rate_mbps else "N/A"),
        ("TX Power", f"{info.tx_power_dbm} dBm" if info.tx_power_dbm else "N/A"),
        ("Power Mgmt", pm_markup),
        ("TX Retries", retry_markup),
        ("Driver", info.driver),
        ("Driver Version", info.driver_version),
        ("Vendor", info.vendor),
    ]

    for field, value in rows:
        table.add_row(field, value)

    return table


def findings_panels(findings: list[DiagnosticFinding]) -> list:
    """Return list of rich renderables (one Panel per finding)."""
    from rich.panel import Panel
    panels = []
    for f in findings:
        color = SEVERITY_COLORS.get(f.severity, "white")
        icon = SEVERITY_ICONS.get(f.severity, "•")
        body = Text()
        body.append(f.detail + "\n\n", style="white")
        body.append("Fix: ", style="bold")
        body.append(f.recommendation, style="bright_cyan")
        panels.append(Panel(
            body,
            title=f"[{color}]{icon} {f.title}[/{color}]",
            border_style=color.replace("bold ", ""),
            expand=True,
        ))
    return panels
