from __future__ import annotations
import re
import time
import io
import statistics
import platform
import urllib.request
import urllib.error
from datetime import datetime
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.text import Text
from ..models import SpeedResult
from ..ui.banner import console
from ..utils import run_cmd

# Public test files (no registration required)
DOWNLOAD_URLS = [
    "https://proof.ovh.net/files/10Mb.dat",
    "http://speedtest.tele2.net/10MB.zip",
    "https://speed.hetzner.de/10MB.bin",
]
UPLOAD_URL = "https://httpbin.org/post"
PING_TARGET = "8.8.8.8"


def _measure_download(url: str, timeout: int = 30) -> float:
    """Return download speed in Mb/s. Returns 0.0 on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "wifi-debugger/1.0"})
        start = time.monotonic()
        total_bytes = 0
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                total_bytes += len(chunk)
        elapsed = time.monotonic() - start
        if elapsed < 0.1 or total_bytes == 0:
            return 0.0
        return (total_bytes * 8) / elapsed / 1_000_000
    except Exception:
        return 0.0


def _measure_upload(url: str, size_mb: int = 5, timeout: int = 30) -> float:
    """Return upload speed in Mb/s."""
    import os
    data = os.urandom(size_mb * 1024 * 1024)
    try:
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={"Content-Type": "application/octet-stream",
                     "User-Agent": "wifi-debugger/1.0"}
        )
        start = time.monotonic()
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
        elapsed = time.monotonic() - start
        if elapsed < 0.1:
            return 0.0
        return (len(data) * 8) / elapsed / 1_000_000
    except Exception:
        return 0.0


def _measure_latency() -> tuple[float, float]:
    """Return (avg_ms, jitter_ms) from 5 pings to 8.8.8.8."""
    count_flag = "-n" if platform.system() == "Windows" else "-c"
    stdout, _, rc = run_cmd(["ping", count_flag, "5", PING_TARGET], timeout=15)
    if rc != 0:
        return 0.0, 0.0

    if platform.system() == "Windows":
        times = [float(m) for m in re.findall(r"time[=<](\d+)ms", stdout)]
    else:
        times = [float(m) for m in re.findall(r"time=([\d.]+) ms", stdout)]

    if not times:
        return 0.0, 0.0
    avg = statistics.mean(times)
    jitter = statistics.stdev(times) if len(times) > 1 else 0.0
    return round(avg, 1), round(jitter, 1)


class SpeedTester:
    def __init__(self):
        pass

    def run(self) -> SpeedResult:
        console.print("[bold cyan]Running speed test...[/bold cyan]")
        download_mbps = 0.0
        upload_mbps = 0.0
        latency_ms = 0.0
        jitter_ms = 0.0

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold]{task.description}"),
            BarColumn(),
            TextColumn("{task.fields[speed]}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            # Latency
            t_lat = progress.add_task("Measuring latency...", total=None, speed="")
            latency_ms, jitter_ms = _measure_latency()
            progress.update(t_lat, description="Latency",
                            speed=f"{latency_ms} ms  jitter {jitter_ms} ms",
                            completed=1, total=1)

            # Download — try each URL until one works
            t_dl = progress.add_task("Download speed...", total=None, speed="")
            for url in DOWNLOAD_URLS:
                dl = _measure_download(url)
                if dl > 0:
                    download_mbps = dl
                    break
            progress.update(t_dl, description="Download",
                            speed=f"{download_mbps:.1f} Mb/s",
                            completed=1, total=1)

            # Upload
            t_ul = progress.add_task("Upload speed...", total=None, speed="")
            upload_mbps = _measure_upload(UPLOAD_URL, size_mb=5)
            progress.update(t_ul, description="Upload",
                            speed=f"{upload_mbps:.1f} Mb/s",
                            completed=1, total=1)

        result = SpeedResult(
            download_mbps=round(download_mbps, 1),
            upload_mbps=round(upload_mbps, 1),
            latency_ms=latency_ms,
            jitter_ms=jitter_ms,
            server="proof.ovh.net / httpbin.org",
            timestamp=datetime.now(),
        )
        self._display(result)
        return result

    def _display(self, r: SpeedResult):
        def _bar(mbps: float, max_mbps: float = 200) -> str:
            pct = min(1.0, mbps / max_mbps)
            filled = round(pct * 20)
            return "█" * filled + "░" * (20 - filled)

        body = Text()
        body.append(f"  Download:  ", style="bold")
        body.append(f"{_bar(r.download_mbps)}  ", style="bright_green")
        body.append(f"{r.download_mbps:.1f} Mb/s\n", style="bold bright_green")
        body.append(f"  Upload:    ", style="bold")
        body.append(f"{_bar(r.upload_mbps)}  ", style="bright_blue")
        body.append(f"{r.upload_mbps:.1f} Mb/s\n", style="bold bright_blue")
        body.append(f"  Latency:   ", style="bold")
        lat_color = "green" if r.latency_ms < 30 else ("yellow" if r.latency_ms < 80 else "red")
        body.append(f"{r.latency_ms} ms  ", style=lat_color)
        body.append(f"(jitter: {r.jitter_ms} ms)\n", style="dim")
        body.append(f"  Server:    {r.server}", style="dim")

        console.print(Panel(body, title="[bold]Speed Test Results[/bold]", border_style="cyan"))
