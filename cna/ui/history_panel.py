"""History panel for CNA terminal UI.

Renders the turn history / replay snapshot list as a Rich Panel,
allowing the player to browse and restore past game states.
Uses Rich library for terminal formatting per CLAUDE.md conventions.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text

from cna.engine.history import GameHistory, format_history_entry


def render_history(history: GameHistory, current_index: int) -> Panel:
    """Render the snapshot history as a Rich Panel.

    Displays a scrollable list of all stored snapshots. The snapshot
    at current_index is highlighted with reverse video style. Each
    entry shows its index, label, turn/stage/phase, and unit count.

    A key legend is displayed at the bottom of the panel.

    Args:
        history: The GameHistory containing snapshots to display.
        current_index: The index of the currently selected snapshot,
            highlighted with reverse style. Clamped to valid range.

    Returns:
        A Rich Panel containing the formatted history list.
    """
    text = Text()
    count = history.count()

    if count == 0:
        text.append("No snapshots recorded yet.", style="dim")
    else:
        # Clamp current_index to valid range
        clamped_index = max(0, min(current_index, count - 1))

        for i in range(count):
            if i > 0:
                text.append("\n")

            state = history.get_snapshot(i)
            label = history.labels()[i]
            line = format_history_entry(i, label, state)

            if i == clamped_index:
                text.append(line, style="reverse")
            else:
                text.append(line)

    # Key legend
    text.append("\n\n")
    text.append("[/] history  [j/k] scroll  [Enter] restore", style="dim")

    return Panel(text, title="History", border_style="yellow")
