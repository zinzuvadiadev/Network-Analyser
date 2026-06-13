from __future__ import annotations
import collections
import threading
import time
from rich.live import Live
from ..platform_layer.base import PlatformBackend
from ..ui.live_display import make_monitor_panel
from ..ui.banner import console


class SignalMonitor:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    def run(self, duration_seconds: int = 0, sample_hz: float = 2.0):
        """
        Run the live signal monitor.
        duration_seconds=0 means run indefinitely until Ctrl+C.
        """
        samples: collections.deque = collections.deque(maxlen=120)
        stop_event = threading.Event()
        interval = 1.0 / sample_hz

        def _sample_loop():
            while not stop_event.is_set():
                dbm = self.backend.get_signal_now(self.interface)
                samples.append(dbm)
                time.sleep(interval)

        sampler = threading.Thread(target=_sample_loop, daemon=True)
        sampler.start()

        stats: dict = {}
        start = time.time()

        try:
            with Live(console=console, refresh_per_second=4) as live:
                while True:
                    if samples:
                        current = samples[-1]
                        sample_list = list(samples)
                        stats = {
                            "min": min(sample_list),
                            "max": max(sample_list),
                            "avg": round(sum(sample_list) / len(sample_list), 1),
                        }
                        live.update(make_monitor_panel(samples, current, stats, self.interface))

                    if duration_seconds and (time.time() - start) >= duration_seconds:
                        break
                    time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            stop_event.set()

        if stats:
            console.print(
                f"\n[bold]Signal summary[/bold] — "
                f"Min: [red]{stats['min']} dBm[/red]  "
                f"Max: [green]{stats['max']} dBm[/green]  "
                f"Avg: [cyan]{stats['avg']} dBm[/cyan]  "
                f"Samples: {len(samples)}"
            )
