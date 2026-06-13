from __future__ import annotations
import csv
import os
import platform
import subprocess
import time
import statistics
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm, FloatPrompt, IntPrompt

from ..models import CoveragePoint
from ..platform_layer.base import PlatformBackend
from ..ui.banner import console


class CoverageVisualizer:
    def __init__(self, backend: PlatformBackend, interface: str):
        self.backend = backend
        self.interface = interface

    # ------------------------------------------------------------------ #
    # Main entry                                                           #
    # ------------------------------------------------------------------ #

    def run(self):
        console.print(Panel(
            "[bold]WiFi Coverage Visualizer[/bold]\n\n"
            "Walk around your room with your laptop and record the signal\n"
            "strength at different positions. The tool will generate a\n"
            "[bold cyan]2D heatmap[/bold cyan] + [bold cyan]interactive 3D surface plot[/bold cyan].\n\n"
            "[dim]You need at least 4 points. 8–16 gives the best heatmap.[/dim]",
            border_style="cyan",
        ))

        room_w = FloatPrompt.ask("  Room width (meters)", default=5.0)
        room_h = FloatPrompt.ask("  Room depth (meters)", default=4.0)

        console.print(
            f"\n[dim]Room set to [bold]{room_w}m × {room_h}m[/bold]. "
            "Coordinates: (0,0) = bottom-left corner.\n"
            "Walk to each position, enter its coordinates, press Enter to record.[/dim]\n"
        )

        points = self._collect_points(room_w, room_h)

        if len(points) < 4:
            console.print("[red]Need at least 4 points to generate a heatmap. Cancelled.[/red]")
            return

        output_path = self._output_path()
        csv_path = output_path.replace(".png", ".csv")

        self._save_csv(points, csv_path)
        console.print(f"[dim]Data saved to {csv_path}[/dim]")

        console.print("\n[bold cyan]Generating heatmap and 3D surface...[/bold cyan]")
        try:
            result_path = self._generate_plot(points, room_w, room_h, output_path)
            console.print(f"[bold green]✓ Saved: {result_path}[/bold green]")
            self._open_image(result_path)
        except Exception as e:
            console.print(f"[red]Plot failed: {e}[/red]")

    # ------------------------------------------------------------------ #
    # Point collection                                                     #
    # ------------------------------------------------------------------ #

    def _collect_points(self, room_w: float, room_h: float) -> list[CoveragePoint]:
        points: list[CoveragePoint] = []

        while True:
            self._print_dot_map(points, room_w, room_h)
            n = len(points) + 1
            console.print(f"[bold]Point {n}[/bold] — enter position (or 'done' to finish):")

            x_raw = Prompt.ask(f"  X position [0 – {room_w}]", default="done")
            if x_raw.lower() in ("done", "d", "q", ""):
                if len(points) >= 4:
                    break
                else:
                    console.print(f"[yellow]Need at least 4 points (have {len(points)}).[/yellow]")
                    continue

            try:
                x = float(x_raw)
                y = float(Prompt.ask(f"  Y position [0 – {room_h}]"))
            except ValueError:
                console.print("[red]Invalid coordinate. Try again.[/red]")
                continue

            x = max(0.0, min(room_w, x))
            y = max(0.0, min(room_h, y))

            input(f"  Stand at ({x:.1f}, {y:.1f}) and press Enter to measure...")

            dbm = self._sample_signal()
            points.append(CoveragePoint(x=x, y=y, signal_dbm=dbm))
            from ..utils import dbm_to_quality
            quality = dbm_to_quality(dbm)
            console.print(f"  [bold green]✓[/bold green] Recorded: ({x:.1f}, {y:.1f}) → "
                          f"[bold]{dbm} dBm[/bold] ({quality})")

        return points

    def _sample_signal(self, n_samples: int = 5, interval: float = 0.5) -> int:
        """Collect n_samples readings and return the median."""
        import sys
        readings = []
        sys.stdout.write("  Measuring")
        sys.stdout.flush()
        for _ in range(n_samples):
            readings.append(self.backend.get_signal_now(self.interface))
            sys.stdout.write(".")
            sys.stdout.flush()
            time.sleep(interval)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return int(statistics.median(readings))

    def _print_dot_map(self, points: list[CoveragePoint], room_w: float, room_h: float):
        """Print a simple ASCII dot-map of recorded positions."""
        if not points:
            return
        cols, rows = 30, 10
        grid = [["·"] * cols for _ in range(rows)]
        for p in points:
            col = round((p.x / room_w) * (cols - 1))
            row = rows - 1 - round((p.y / room_h) * (rows - 1))
            col = max(0, min(cols - 1, col))
            row = max(0, min(rows - 1, row))
            # Encode signal quality into display char
            from ..utils import dbm_to_quality
            q = dbm_to_quality(p.signal_dbm)
            char = "G" if q == "Excellent" else ("g" if q == "Good" else
                   ("·" if q == "Fair" else "x"))
            grid[row][col] = char

        console.print("\n[dim]  Map (G=Excellent g=Good ·=Fair x=Poor) — N={0} points[/dim]".format(len(points)))
        for row in grid:
            console.print("  " + " ".join(row))
        console.print()

    # ------------------------------------------------------------------ #
    # Plot generation                                                      #
    # ------------------------------------------------------------------ #

    def _generate_plot(self, points: list[CoveragePoint], room_w: float, room_h: float,
                        output_path: str) -> str:
        import numpy as np
        from scipy.interpolate import Rbf
        from scipy.ndimage import gaussian_filter
        import matplotlib
        matplotlib.use("Agg")   # non-interactive backend for saving
        import matplotlib.pyplot as plt
        import matplotlib.colors as mcolors
        from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

        xs = np.array([p.x for p in points])
        ys = np.array([p.y for p in points])
        zs = np.array([p.signal_dbm for p in points], dtype=float)

        # Interpolation grid at ~0.05m resolution
        grid_x, grid_y = np.mgrid[0:room_w:100j, 0:room_h:100j]

        rbf = Rbf(xs, ys, zs, function="multiquadric", smooth=0.5)
        grid_z = rbf(grid_x, grid_y)
        grid_z = np.clip(grid_z, -100, -30)
        grid_z = gaussian_filter(grid_z, sigma=2)

        vmin, vmax = -95, -35
        cmap = mcolors.LinearSegmentedColormap.from_list(
            "wifi",
            ["#d73027", "#f46d43", "#fdae61", "#fee08b", "#d9ef8b", "#a6d96a", "#1a9850"],
        )

        fig = plt.figure(figsize=(18, 8))
        fig.patch.set_facecolor("#1a1a2e")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        fig.suptitle(f"WiFi Coverage Map — {timestamp}", color="white", fontsize=14, y=0.98)

        # ---- Left: 2D heatmap ---- #
        ax1 = fig.add_subplot(1, 2, 1)
        ax1.set_facecolor("#16213e")
        im = ax1.imshow(
            grid_z.T,
            origin="lower",
            extent=[0, room_w, 0, room_h],
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            aspect="auto",
            interpolation="bilinear",
        )
        sc = ax1.scatter(xs, ys, c=zs, cmap=cmap, vmin=vmin, vmax=vmax,
                         edgecolors="white", linewidths=1.5, s=120, zorder=5)
        for p in points:
            ax1.annotate(f"{p.signal_dbm}", (p.x, p.y),
                         textcoords="offset points", xytext=(6, 4),
                         fontsize=8, color="white",
                         bbox=dict(boxstyle="round,pad=0.2", fc="black", alpha=0.5))
        cbar = plt.colorbar(im, ax=ax1, label="Signal (dBm)")
        cbar.ax.yaxis.label.set_color("white")
        cbar.ax.tick_params(colors="white")
        ax1.set_xlabel("Width (m)", color="white")
        ax1.set_ylabel("Depth (m)", color="white")
        ax1.set_title("2D Coverage Heatmap", color="white")
        ax1.tick_params(colors="white")
        ax1.spines[:].set_color("#444")
        ax1.grid(True, alpha=0.2, color="white")

        # ---- Right: 3D surface ---- #
        ax2 = fig.add_subplot(1, 2, 2, projection="3d")
        ax2.set_facecolor("#16213e")
        surf = ax2.plot_surface(
            grid_x, grid_y, grid_z,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            alpha=0.85,
            linewidth=0,
            antialiased=True,
        )
        # Measurement point spikes
        ax2.scatter(xs, ys, zs, c=zs, cmap=cmap, vmin=vmin, vmax=vmax,
                    s=80, edgecolors="white", linewidths=1.5, zorder=6, depthshade=False)
        for p in points:
            ax2.plot([p.x, p.x], [p.y, p.y], [grid_z.min(), p.signal_dbm],
                     color="white", alpha=0.4, linewidth=0.8)

        ax2.set_xlabel("Width (m)", color="white", labelpad=8)
        ax2.set_ylabel("Depth (m)", color="white", labelpad=8)
        ax2.set_zlabel("Signal (dBm)", color="white", labelpad=8)
        ax2.set_title("3D Signal Landscape", color="white")
        ax2.tick_params(colors="white")
        ax2.view_init(elev=35, azim=-60)
        ax2.set_facecolor("#16213e")
        # Pane colors
        ax2.xaxis.pane.fill = False
        ax2.yaxis.pane.fill = False
        ax2.zaxis.pane.fill = False
        ax2.xaxis.pane.set_edgecolor("#333")
        ax2.yaxis.pane.set_edgecolor("#333")
        ax2.zaxis.pane.set_edgecolor("#333")
        fig.colorbar(surf, ax=ax2, label="Signal (dBm)", shrink=0.6).ax.yaxis.label.set_color("white")

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
        plt.close(fig)
        return output_path

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _output_path(self) -> str:
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        base = Path.home() / f"wifi_coverage_{ts}.png"
        return str(base)

    def _save_csv(self, points: list[CoveragePoint], path: str):
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["x_m", "y_m", "signal_dbm", "timestamp"])
            for p in points:
                writer.writerow([p.x, p.y, p.signal_dbm, p.timestamp.isoformat()])

    def _open_image(self, path: str):
        try:
            if platform.system() == "Linux":
                subprocess.Popen(["xdg-open", path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif platform.system() == "Windows":
                os.startfile(path)
        except Exception:
            pass
        console.print(f"[dim]Image saved to: {path}[/dim]")
