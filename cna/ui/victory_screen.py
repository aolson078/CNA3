"""End-of-game victory screen for CNA.

Renders a Rich Panel showing the winner, victory level, reason, and
final game statistics when a scenario reaches its conclusion.

Case 60.8 — Victory conditions are checked at the end of the scenario's
final Game-Turn.
"""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cna.data.scenarios.victory import VictoryLevel, VictoryResult
from cna.engine.game_state import GameState, Side
from cna.rules.abstract.supply import get_supply_pool


_SIDE_STYLES: dict[Side, str] = {
    Side.AXIS: "bold red",
    Side.COMMONWEALTH: "bold cyan",
}

_LEVEL_STYLES: dict[VictoryLevel, str] = {
    VictoryLevel.DRAW: "dim white",
    VictoryLevel.TACTICAL: "bold yellow",
    VictoryLevel.DECISIVE: "bold magenta",
    VictoryLevel.STRATEGIC: "bold red on white",
}


def render_victory(result: VictoryResult, state: GameState) -> Panel:
    """Render the end-of-game victory screen as a Rich Panel.

    Case 60.8 — Displays winner, victory level, reason, and final stats.
    """
    headline = Text()
    if result.winner is not None:
        style = _SIDE_STYLES.get(result.winner, "bold white")
        headline.append(result.winner.value.upper(), style=style)
        headline.append(" ")
    level_style = _LEVEL_STYLES.get(result.level, "bold white")
    headline.append(f"{result.level.value.upper()} VICTORY", style=level_style)

    reason_text = Text(result.reason, style="italic")

    stats = Table(title="Final Statistics", expand=True, show_edge=False)
    stats.add_column("", style="bold")
    stats.add_column("Axis", justify="right", style="red")
    stats.add_column("Commonwealth", justify="right", style="cyan")

    scenario_length = state.extras.get("scenario_length_turns", state.game_turn)
    stats.add_row("Turns played", str(min(state.game_turn, scenario_length)), "")

    ax_units = [u for u in state.units.values() if u.side == Side.AXIS]
    cw_units = [u for u in state.units.values() if u.side == Side.COMMONWEALTH]
    ax_on_map = sum(1 for u in ax_units if u.position is not None and u.current_toe > 0)
    cw_on_map = sum(1 for u in cw_units if u.position is not None and u.current_toe > 0)
    stats.add_row("Units on map", str(ax_on_map), str(cw_on_map))

    ax_toe = sum(u.current_toe for u in ax_units)
    cw_toe = sum(u.current_toe for u in cw_units)
    stats.add_row("Total TOE strength", str(ax_toe), str(cw_toe))

    ax_supply = get_supply_pool(state, Side.AXIS)
    cw_supply = get_supply_pool(state, Side.COMMONWEALTH)
    stats.add_row("Ammo remaining", str(ax_supply.ammo), str(cw_supply.ammo))
    stats.add_row("Fuel remaining", str(ax_supply.fuel), str(cw_supply.fuel))

    body = Group(headline, Text(""), reason_text, Text(""), stats)
    return Panel(
        body,
        title="[bold]Game Over[/bold]",
        border_style="bright_yellow",
        padding=(1, 2),
    )
