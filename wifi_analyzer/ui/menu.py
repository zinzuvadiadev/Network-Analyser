from __future__ import annotations
from rich.panel import Panel
from rich.text import Text
from rich.prompt import IntPrompt
from .banner import console


MENU_ITEMS = [
    (1, "Scan nearby networks"),
    (2, "Analyze current connection"),
    (3, "Real-time signal monitor"),
    (4, "Speed test"),
    (5, "Channel congestion analysis"),
    (6, "Power management check / fix"),
    (7, "Coverage visualizer  (2D heatmap + 3D surface)"),
    (8, "Adapter capabilities"),
    (9, "Full diagnostics report"),
    (0, "Exit"),
]


def show_menu() -> int:
    body = Text()
    for num, label in MENU_ITEMS:
        style = "bold cyan" if num != 0 else "dim"
        body.append(f"  [{num}]  {label}\n", style=style)

    console.print(Panel(body, title="[bold]Main Menu[/bold]", border_style="cyan",
                         expand=False))
    return IntPrompt.ask("Choose", choices=[str(n) for n, _ in MENU_ITEMS], show_choices=False)
