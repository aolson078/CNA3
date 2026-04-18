"""Section 4.1 -- Strategic Minimap View

Provides a compact overview of the entire operational area, showing unit
density, supply status, named locations, and the front line at a glance.
"""

from __future__ import annotations

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cna.engine.game_state import (
    GameState,
    HexCoord,
    Side,
    TerrainType,
    UnitType,
)
from cna.rules.stacking import stacking_points, current_stacking
from cna.rules.abstract.supply import is_in_supply
from cna.ui.dashboard import TERRAIN_GLYPHS
from cna.ui.views import GameView, HexView


# ---- Named-location abbreviations ----------------------------------------

# Map of known location names to 3-character abbreviations.
_ABBREVIATIONS: dict[str, str] = {
    "Tobruk": "Tob",
    "Bardia": "Bar",
    "Benghazi": "Ben",
    "Tripoli": "Tri",
    "Alexandria": "Alx",
    "Mersa Matruh": "MrM",
    "El Agheila": "Agh",
    "Gazala": "Gaz",
    "Derna": "Der",
    "Sidi Barrani": "SBr",
    "Halfaya": "Hal",
    "Mechili": "Mch",
    "Msus": "Mss",
    "El Alamein": "Alm",
    "Sollum": "Sol",
    "Buq Buq": "BuB",
    "Fort Capuzzo": "Cap",
}


def abbreviate_name(name: str) -> str:
    """Case 4.1 -- Return a 3-character abbreviation for a named location.

    Looks up the name in a table of known abbreviations. If not found,
    returns the first three characters of the name.
    """
    return _ABBREVIATIONS.get(name, name[:3])


# ---- Density classification -----------------------------------------------

class DensityLevel:
    """Case 4.1 -- Classification of unit density at a hex."""

    EMPTY = "empty"
    LIGHT = "light"      # 1-3 SP
    MEDIUM = "medium"    # 4-7 SP
    HEAVY = "heavy"      # 8+ SP


def classify_density(sp: int) -> str:
    """Case 4.1 -- Classify stacking-point total into a density level.

    Args:
        sp: Total stacking points in a hex for one side.

    Returns:
        One of the DensityLevel constants.
    """
    if sp <= 0:
        return DensityLevel.EMPTY
    elif sp <= 3:
        return DensityLevel.LIGHT
    elif sp <= 7:
        return DensityLevel.MEDIUM
    else:
        return DensityLevel.HEAVY


def _density_style(density: str, side: Side) -> str:
    """Case 4.1 -- Return a Rich style string for a density/side combination.

    Color-codes hexes by unit density:
      - Empty: dim terrain glyph
      - Light (1-3 SP): side color dim
      - Medium (4-7 SP): side color normal
      - Heavy (8+ SP): side color bold + reverse
    """
    color = "blue" if side == Side.ALLIED else "red"
    match density:
        case DensityLevel.LIGHT:
            return f"dim {color}"
        case DensityLevel.MEDIUM:
            return color
        case DensityLevel.HEAVY:
            return f"bold reverse {color}"
        case _:
            return "dim white"


# ---- Front line detection --------------------------------------------------

def compute_front_line(state: GameState) -> set[HexCoord]:
    """Case 4.1 -- Compute front-line hexes where opposing forces are adjacent.

    A hex is on the front line if it contains combat units (non-supply,
    non-air) for one side and at least one of its six neighbors contains
    combat units for the opposing side.

    Args:
        state: Current game state.

    Returns:
        Set of HexCoord values that lie on the front line.
    """
    # Non-combat unit types that do not create a front line
    non_combat_types = {UnitType.SUPPLY, UnitType.AIR}

    # Build per-side sets of hexes with combat units
    side_hexes: dict[Side, set[HexCoord]] = {
        Side.ALLIED: set(),
        Side.AXIS: set(),
    }

    for coord, hex_state in state.hexes.items():
        for uid in hex_state.units:
            unit = state.units.get(uid)
            if unit is not None and unit.unit_type not in non_combat_types:
                side_hexes[unit.side].add(coord)

    front_line: set[HexCoord] = set()

    for side in (Side.ALLIED, Side.AXIS):
        enemy = Side.AXIS if side == Side.ALLIED else Side.ALLIED
        for coord in side_hexes[side]:
            for neighbor in coord.neighbors():
                if neighbor in side_hexes[enemy]:
                    front_line.add(coord)
                    front_line.add(neighbor)
                    break  # This hex is already flagged; move on

    return front_line


# ---- Hex cell rendering ----------------------------------------------------

def _render_strategic_cell(
    hv: HexView,
    state: GameState,
    front_line: set[HexCoord],
) -> Text:
    """Case 4.1 -- Render a single hex cell for the strategic minimap.

    Each cell is 3 characters wide. Priority order:
      1. Supply warning '!' overlay (red) if unsupplied friendly units
      2. Unit density coloring by dominant side
      3. Named location abbreviated label
      4. Dim terrain glyph

    Front-line hexes get a yellow border marker: the cell text is
    wrapped with yellow brackets-style highlighting.
    """
    coord = hv.coord
    is_front = coord in front_line

    # Determine dominant side and total SP per side
    allied_sp = 0
    axis_sp = 0
    has_unsupplied = False

    for uv in hv.units:
        if uv.side == Side.ALLIED:
            allied_sp += uv.stacking_points
        else:
            axis_sp += uv.stacking_points
        if not uv.in_supply:
            has_unsupplied = True

    total_sp = allied_sp + axis_sp

    # Determine which side dominates this hex (by SP)
    if total_sp > 0:
        dominant_side = Side.ALLIED if allied_sp >= axis_sp else Side.AXIS
        dominant_sp = max(allied_sp, axis_sp)
        density = classify_density(dominant_sp)
        style = _density_style(density, dominant_side)

        # Supply warning overlay
        if has_unsupplied:
            cell = Text(" ! ", style="bold red")
        else:
            # Show density indicator
            match density:
                case DensityLevel.LIGHT:
                    cell = Text(" . ", style=style)
                case DensityLevel.MEDIUM:
                    cell = Text(" o ", style=style)
                case DensityLevel.HEAVY:
                    cell = Text(" # ", style=style)
                case _:
                    cell = Text("   ")
    elif hv.name:
        abbrev = abbreviate_name(hv.name)
        cell = Text(f"{abbrev:^3}"[:3], style="bold white")
    else:
        glyph = TERRAIN_GLYPHS.get(hv.terrain, "?")
        cell = Text(f" {glyph} ", style="dim white")

    # Front-line marker: override style to add yellow pipe borders
    if is_front:
        inner_char = cell.plain[1] if len(cell.plain) > 1 else " "
        inner_style = cell.style or "default"
        result = Text()
        result.append("|", style="bold yellow")
        result.append(inner_char, style=inner_style)
        result.append("|", style="bold yellow")
        return result

    return cell


# ---- Main render function ---------------------------------------------------

def render_strategic_map(view: GameView, state: GameState) -> Panel:
    """Case 4.1 -- Render the strategic minimap as a Rich Panel.

    Produces a compact overview of the entire operational area using a
    Rich Table.grid(). Each cell is 3 characters wide and shows:

      - Unit density color-coded by side (dim/normal/bold+reverse)
      - Named location abbreviated labels (e.g. 'Tob' for Tobruk)
      - Supply warnings ('!' in red) for unsupplied friendly units
      - Front-line markers (yellow '|' borders) where both sides adjoin

    Args:
        view: The GameView containing hex data to render.
        state: The full GameState, needed for supply and front-line checks.

    Returns:
        A Rich Panel wrapping the strategic minimap grid.
    """
    front_line = compute_front_line(state)

    min_col, min_row, max_col, max_row = view.bounds

    grid = Table.grid(padding=0)
    num_cols = max_col - min_col + 1
    for _ in range(num_cols):
        grid.add_column(width=3, no_wrap=True)

    for row in range(min_row, max_row + 1):
        cells: list[Text] = []
        for col in range(min_col, max_col + 1):
            coord = HexCoord(col, row)
            hv = view.hex_views.get(coord)
            if hv is not None:
                cells.append(
                    _render_strategic_cell(hv, state, front_line)
                )
            else:
                cells.append(Text("   "))
        grid.add_row(*cells)

    title = f"Strategic Overview  Turn {view.turn}"
    return Panel(
        grid,
        title=title,
        border_style="cyan",
        subtitle="Density: [dim].[/] light  [default]o[/] med  [bold reverse]#[/] heavy  [bold red]![/] no supply  [bold yellow]|[/] front",
    )
