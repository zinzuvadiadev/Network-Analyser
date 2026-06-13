"""WiFi Debugger & Analyzer — Entry point."""
from __future__ import annotations
import argparse
import sys

from .platform_layer import get_platform_backend
from .ui.banner import print_banner, console
from .ui.menu import show_menu
from .modules.scanner import NetworkScanner
from .modules.connection import ConnectionAnalyzer
from .modules.signal_monitor import SignalMonitor
from .modules.speed_test import SpeedTester
from .modules.channel_analyzer import ChannelAnalyzer
from .modules.power_manager import PowerManager
from .modules.coverage import CoverageVisualizer
from .modules.adapter_info import AdapterInfo
from .modules.diagnostics import DiagnosticsEngine


def _detect_interface(backend) -> str:
    ifaces = backend.get_wifi_interfaces()
    if not ifaces:
        console.print("[red]No WiFi interfaces found. Is WiFi enabled?[/red]")
        sys.exit(1)
    if len(ifaces) == 1:
        return ifaces[0]
    console.print("[bold]Multiple WiFi interfaces found:[/bold]")
    for i, iface in enumerate(ifaces, 1):
        console.print(f"  [{i}] {iface}")
    from rich.prompt import IntPrompt
    choice = IntPrompt.ask("Select interface", choices=[str(i) for i in range(1, len(ifaces)+1)])
    return ifaces[choice - 1]


def _run_option(option: int, backend, interface: str):
    if option == 1:
        NetworkScanner(backend, interface).scan()
    elif option == 2:
        ConnectionAnalyzer(backend, interface).analyze()
    elif option == 3:
        from rich.prompt import IntPrompt
        dur = IntPrompt.ask("Duration in seconds (0 = run until Ctrl+C)", default=0)
        SignalMonitor(backend, interface).run(duration_seconds=dur)
    elif option == 4:
        SpeedTester().run()
    elif option == 5:
        ChannelAnalyzer(backend, interface).analyze()
    elif option == 6:
        PowerManager(backend, interface).check_and_display()
    elif option == 7:
        CoverageVisualizer(backend, interface).run()
    elif option == 8:
        AdapterInfo(backend, interface).display()
    elif option == 9:
        DiagnosticsEngine(backend, interface).run()
    elif option == 0:
        console.print("[dim]Goodbye.[/dim]")
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(
        prog="wifi_analyzer",
        description="WiFi Debugger & Analyzer — cross-platform network diagnostics",
    )
    parser.add_argument("--interface", "-i", help="WiFi interface name (auto-detected if omitted)")
    parser.add_argument("--scan", action="store_true", help="Scan nearby networks and exit")
    parser.add_argument("--diagnose", action="store_true", help="Run full diagnostics and exit")
    parser.add_argument("--monitor", type=int, metavar="SECONDS",
                        help="Run real-time signal monitor for N seconds (0 = indefinite)")
    parser.add_argument("--ui", action="store_true",
                        help="Launch the web UI (React dashboard) on http://localhost:7070")
    args = parser.parse_args()

    print_banner()

    try:
        backend = get_platform_backend()
    except RuntimeError as e:
        console.print(f"[red]{e}[/red]")
        sys.exit(1)

    interface = args.interface or _detect_interface(backend)
    console.print(f"[dim]Using interface: [bold]{interface}[/bold][/dim]\n")

    # Web UI mode
    if args.ui:
        import webbrowser, threading
        from .api import serve
        console.print("[bold cyan]Starting WiFi Debugger Web UI...[/bold cyan]")
        console.print("[dim]API: http://localhost:7070  |  UI: http://localhost:5173[/dim]")
        console.print("[dim]Run 'npm run dev' in wifi_ui/ to start the frontend.[/dim]\n")
        serve(host="127.0.0.1", port=7070)
        return

    # Non-interactive modes
    if args.scan:
        NetworkScanner(backend, interface).scan()
        return
    if args.diagnose:
        DiagnosticsEngine(backend, interface).run()
        return
    if args.monitor is not None:
        SignalMonitor(backend, interface).run(duration_seconds=args.monitor)
        return

    # Interactive menu loop
    while True:
        console.print()
        option = show_menu()
        console.print()
        try:
            _run_option(option, backend, interface)
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/dim]")
        console.print()
        if option != 0:
            input("  Press Enter to return to menu...")


if __name__ == "__main__":
    main()
