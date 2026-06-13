from __future__ import annotations
from typing import Optional
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from ..models import DiagnosticFinding, AccessPoint, ConnectionInfo
from ..platform_layer.base import PlatformBackend
from ..ui.tables import findings_panels
from ..ui.banner import console, SEVERITY_COLORS, SEVERITY_ICONS


class DiagnosticsEngine:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    def run(self) -> list[DiagnosticFinding]:
        console.print("[bold cyan]Running full diagnostics...[/bold cyan]\n")

        aps = self.backend.scan_networks(self.interface)
        conn = self.backend.get_connection_info(self.interface)
        adapter = self.backend.get_adapter_capabilities(self.interface)

        findings: list[DiagnosticFinding] = []

        if conn is None:
            findings.append(DiagnosticFinding(
                severity="critical",
                category="connection",
                title="Not Connected to WiFi",
                detail="No active WiFi connection was detected on this interface.",
                recommendation="Connect to a WiFi network first.",
            ))
            self._display(findings)
            return findings

        findings += self._check_band_selection(conn, aps, adapter)
        findings += self._check_power_management(conn)
        findings += self._check_signal_strength(conn)
        findings += self._check_channel_congestion(conn, aps)
        findings += self._check_tx_retries(conn)
        findings += self._check_channel_width(conn, aps)
        findings += self._check_same_ssid_bands(aps)
        findings += self._check_driver(adapter)

        if not findings:
            findings.append(DiagnosticFinding(
                severity="ok",
                category="general",
                title="All Checks Passed",
                detail="No issues were detected with your WiFi configuration.",
                recommendation="Your WiFi setup looks good. If you experience issues, "
                               "try running a speed test and signal monitor.",
            ))

        self._display(findings)
        return findings

    # ------------------------------------------------------------------ #
    # Rules                                                                #
    # ------------------------------------------------------------------ #

    def _check_band_selection(self, conn: ConnectionInfo, aps: list[AccessPoint],
                               adapter: dict) -> list[DiagnosticFinding]:
        if conn.band != "2.4GHz":
            return []
        # Check if a 5GHz AP exists with the same or similar SSID
        five_ghz_aps = [a for a in aps if a.band in ("5GHz", "6GHz") and a.ssid != "<hidden>"]
        if not five_ghz_aps:
            return []
        best_5 = max(five_ghz_aps, key=lambda a: a.signal_dbm)
        supported = adapter.get("supported_bands", [])
        # Only skip if we KNOW the adapter doesn't support 5GHz (non-empty list without 5GHz)
        if supported and "5GHz" not in supported and "6GHz" not in supported:
            return []  # adapter doesn't support 5GHz — not a config issue

        same_prefix = [a for a in five_ghz_aps if
                       conn.ssid.lower().replace("_2.4", "").replace("_24g", "") in
                       a.ssid.lower() or a.ssid.lower() in conn.ssid.lower()]
        five_ssid = same_prefix[0].ssid if same_prefix else best_5.ssid

        return [DiagnosticFinding(
            severity="critical",
            category="band",
            title="Connected to 2.4GHz — 5GHz Available",
            detail=(
                f"You are on {conn.ssid} (2.4GHz, Ch {conn.channel}) but "
                f"a 5GHz network is visible: '{five_ssid}' ({best_5.signal_dbm} dBm).\n"
                f"2.4GHz is slower and more congested. 5GHz provides 3–5× higher throughput "
                f"at similar range. This is a primary cause of the phone vs laptop speed gap."
            ),
            recommendation=(
                f"Forget '{conn.ssid}' and connect to '{five_ssid}'. "
                f"On Linux: nmcli device wifi connect '{five_ssid}'"
            ),
        )]

    def _check_power_management(self, conn: ConnectionInfo) -> list[DiagnosticFinding]:
        if not conn.power_management:
            return []
        return [DiagnosticFinding(
            severity="critical",
            category="power_management",
            title="WiFi Power Management is ON",
            detail=(
                "Your adapter is throttling its radio to save battery. "
                "This causes throughput to drop by 5–10× and adds latency spikes. "
                "Phones do not have this issue as they manage power differently. "
                "This alone explains the phone vs laptop speed gap in your apartment corner."
            ),
            recommendation=f"sudo iwconfig {conn.interface} power off",
        )]

    def _check_signal_strength(self, conn: ConnectionInfo) -> list[DiagnosticFinding]:
        dbm = conn.signal_dbm
        if dbm >= -65:
            return []
        if dbm >= -75:
            return [DiagnosticFinding(
                severity="warning",
                category="signal",
                title="Weak Signal",
                detail=f"Signal is {dbm} dBm (Fair). This reduces throughput and increases errors.",
                recommendation="Move closer to the router, or add a WiFi extender / mesh node.",
            )]
        return [DiagnosticFinding(
            severity="critical",
            category="signal",
            title="Very Weak Signal",
            detail=(
                f"Signal is {dbm} dBm — well below the usable threshold (-75 dBm). "
                f"At this level, the connection is unreliable and throughput will be minimal."
            ),
            recommendation="Move closer to the router. Consider a mesh node or repeater near your problem corner.",
        )]

    def _check_channel_congestion(self, conn: ConnectionInfo,
                                   aps: list[AccessPoint]) -> list[DiagnosticFinding]:
        from ..utils import overlapping_channels_24
        if conn.band != "2.4GHz":
            return []
        competing = [a for a in aps
                     if a.channel in overlapping_channels_24(conn.channel)
                     and not a.is_connected
                     and a.signal_dbm > -80]
        if len(competing) <= 2:
            return []
        return [DiagnosticFinding(
            severity="warning",
            category="channel",
            title=f"Channel Congestion — {len(competing)} Competing Networks",
            detail=(
                f"Channel {conn.channel} (2.4GHz) has {len(competing)} nearby networks "
                f"causing interference. 2.4GHz has only 3 non-overlapping channels: 1, 6, 11."
            ),
            recommendation=(
                f"Log into your router and change its WiFi channel to one of: 1, 6, 11 — "
                f"whichever is least occupied (use the channel analyzer for details)."
            ),
        )]

    def _check_tx_retries(self, conn: ConnectionInfo) -> list[DiagnosticFinding]:
        if conn.retry_excessive <= 50:
            return []
        return [DiagnosticFinding(
            severity="warning",
            category="signal",
            title=f"High TX Retry Count ({conn.retry_excessive})",
            detail=(
                "A high number of excessive TX retries means many packets are failing "
                "on the first send, indicating RF interference, weak signal, or congestion. "
                "Throughput is reduced as the adapter retransmits lost packets."
            ),
            recommendation="Reduce interference (change channel, move closer) or disable PM.",
        )]

    def _check_channel_width(self, conn: ConnectionInfo,
                              aps: list[AccessPoint]) -> list[DiagnosticFinding]:
        if conn.band != "2.4GHz":
            return []
        has_5ghz_ap = any(a.band in ("5GHz", "6GHz") for a in aps)
        if not has_5ghz_ap:
            return []
        width = conn.channel_width
        if width and "40" not in width and "80" not in width:
            return [DiagnosticFinding(
                severity="warning",
                category="channel",
                title=f"Narrow Channel Width ({width})",
                detail=(
                    f"Connected at {width} on 2.4GHz. 5GHz supports 80MHz channels, "
                    f"which offer 4× the bandwidth. Your phone likely uses 5GHz 80MHz."
                ),
                recommendation="Switch to 5GHz for wider channel support and higher throughput.",
            )]
        return []

    def _check_same_ssid_bands(self, aps: list[AccessPoint]) -> list[DiagnosticFinding]:
        """Detect routers broadcasting same SSID on 2.4 and 5GHz (band steering confusion)."""
        ssid_bands: dict[str, set] = {}
        for ap in aps:
            if ap.ssid and ap.ssid != "<hidden>":
                ssid_bands.setdefault(ap.ssid, set()).add(ap.band)
        mixed = [s for s, bands in ssid_bands.items() if "2.4GHz" in bands and "5GHz" in bands]
        if not mixed:
            return []
        return [DiagnosticFinding(
            severity="info",
            category="band",
            title="Router Uses Same SSID for 2.4GHz and 5GHz",
            detail=(
                f"Network(s) {', '.join(repr(s) for s in mixed[:3])} appear on both bands. "
                f"Some devices (especially laptops) get stuck on 2.4GHz even when 5GHz is better."
            ),
            recommendation=(
                "In your router settings, give the 5GHz network a distinct name "
                "(e.g., append '_5G'). This forces you to deliberately choose the faster band."
            ),
        )]

    def _check_driver(self, adapter: dict) -> list[DiagnosticFinding]:
        driver = adapter.get("driver", "Unknown")
        if driver == "Unknown":
            return [DiagnosticFinding(
                severity="info",
                category="driver",
                title="Driver Info Unavailable",
                detail="Could not determine the WiFi driver. Run with elevated privileges for full details.",
                recommendation="Try: nmcli device show <interface> | grep DRIVER",
            )]
        return []

    # ------------------------------------------------------------------ #
    # Display                                                              #
    # ------------------------------------------------------------------ #

    def _display(self, findings: list[DiagnosticFinding]):
        critical = [f for f in findings if f.severity == "critical"]
        warnings = [f for f in findings if f.severity == "warning"]
        info = [f for f in findings if f.severity in ("info", "ok")]

        for finding in critical + warnings + info:
            for panel in findings_panels([finding]):
                console.print(panel)

        # Summary
        console.print(Rule())
        summary = Text()
        if critical:
            summary.append(f"  {len(critical)} critical  ", style="bold red")
        if warnings:
            summary.append(f"  {len(warnings)} warning(s)  ", style="bold yellow")
        if not critical and not warnings:
            summary.append("  All clear — no issues found  ", style="bold green")
        console.print(Panel(summary, title="[bold]Diagnostics Summary[/bold]",
                            border_style="cyan", expand=False))
