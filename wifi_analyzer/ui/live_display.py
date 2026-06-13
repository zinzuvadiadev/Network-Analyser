"""Braille-graph live signal monitor display."""
from __future__ import annotations
import collections
from rich.text import Text
from rich.panel import Panel
from rich.layout import Layout
from rich.console import Console


# Braille dot-to-bit mapping:
#  1(0x01) 4(0x08)
#  2(0x02) 5(0x10)
#  3(0x04) 6(0x20)
#  7(0x40) 8(0x80)
_BRAILLE_BASE = 0x2800
_DOT_BITS = [
    [0x01, 0x08],
    [0x02, 0x10],
    [0x04, 0x20],
    [0x40, 0x80],
]


def _encode_braille(pixels: list[list[bool]]) -> str:
    """pixels is 4 rows × 2 cols of bool. Returns one braille character."""
    code = _BRAILLE_BASE
    for row in range(4):
        for col in range(2):
            if pixels[row][col]:
                code |= _DOT_BITS[row][col]
    return chr(code)


def build_braille_graph(samples: collections.deque, min_dbm: int = -100, max_dbm: int = -30,
                         width_chars: int = 60) -> Text:
    """
    Build a scrolling braille sparkline from signal samples.
    Each braille char is 2 columns × 4 rows of dots.
    """
    # Normalize samples to 0..7 (8 pixel rows)
    def normalize(v: int) -> int:
        clamped = max(min_dbm, min(max_dbm, v))
        return round((clamped - min_dbm) / (max_dbm - min_dbm) * 7)

    sample_list = list(samples)
    # We need width_chars * 2 samples (2 columns per char)
    needed = width_chars * 2
    # Pad left with copies of first sample if not enough data
    if len(sample_list) < needed:
        pad = [sample_list[0]] * (needed - len(sample_list)) if sample_list else [-100] * needed
        sample_list = pad + sample_list
    sample_list = sample_list[-needed:]

    result = Text()
    for i in range(0, needed, 2):
        left = normalize(sample_list[i])
        right = normalize(sample_list[i + 1] if i + 1 < needed else sample_list[i])
        # Build 4×2 pixel grid: lit if pixel_row <= normalized_value
        # (graph fills from bottom up)
        pixels = [[False, False] for _ in range(4)]
        for row in range(4):
            pixel_row = 7 - row  # invert: row 0 = top = high signal
            pixels[row][0] = left >= pixel_row
            pixels[row][1] = right >= pixel_row
        char = _encode_braille(pixels)

        # Color by average signal level
        avg = (sample_list[i] + sample_list[i + 1]) / 2
        if avg >= -60:
            style = "bright_green"
        elif avg >= -75:
            style = "yellow"
        else:
            style = "red"
        result.append(char, style=style)

    return result


def make_monitor_panel(samples: collections.deque, current: int,
                        stats: dict, interface: str) -> Panel:
    from ..utils import dbm_to_quality
    from .banner import SIGNAL_COLORS

    quality = dbm_to_quality(current)
    color = SIGNAL_COLORS.get(quality, "white")
    graph = build_braille_graph(samples, width_chars=55)

    body = Text()
    body.append("Signal over time:\n", style="dim")
    body.append_text(graph)
    body.append("\n\n")
    body.append(f"Current: ", style="dim")
    body.append(f"{current} dBm  {quality}", style=f"bold {color}")
    body.append(f"   Min: {stats.get('min', '—')} dBm", style="dim")
    body.append(f"   Max: {stats.get('max', '—')} dBm", style="dim")
    body.append(f"   Avg: {stats.get('avg', '—')} dBm", style="dim")
    body.append(f"\n\nPress Ctrl+C to stop", style="dim italic")

    return Panel(body, title=f"[bold cyan]Live Signal Monitor — {interface}[/bold cyan]",
                 border_style="cyan")
