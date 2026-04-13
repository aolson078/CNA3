"""Rich-based dashboard renderers for the CNA terminal UI.

Renders a GameView (cna/ui/views.py) to a Rich Layout. All panels are
pure functions of a GameView so they're easy to test and compose.

Layout (top-down):
  - Header bar: turn / stage / phase / active side / weather / initiative.
  - Body (three columns):
      left:   Map panel (ASCII hex grid).
      middle: Selected-hex panel (stack details + terrain/controller).
      right:  OOB panel (friendly full, enemy opaque counts).
  - Footer:
      phase log (tail of turn_log).
      command hint line.

Nothing in this module mutates the GameView or GameState. Input handling
lives in cna/ui/app.py (to be added with the first rules module).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from rich.console import Group, RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cna.engine.game_state import (
    CohesionLevel,
    HexCoord,
    LogEntry,
    Phase,
    ReserveStatus,
    Side,
    TerrainType,
    WeatherState,
)
from cna.ui.views import GameView, HexView, UnitView


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------


SIDE_STYLES: dict[Side, str] = {
    Side.AXIS: "bold red",
    Side.COMMONWEALTH: "bold cyan",
}


TERRAIN_GLYPHS: dict[TerrainType, str] = {
    TerrainType.DESERT: ".",
    TerrainType.ROUGH: ",",
    TerrainType.ESCARPMENT: "=",
    TerrainType.MOUNTAIN: "^",
    TerrainType.SALT_MARSH: "~",
    TerrainType.DEPRESSION: "v",
    TerrainType.OASIS: "o",
    TerrainType.TOWN: "t",
    TerrainType.CITY: "C",
    TerrainType.PORT: "P",
    TerrainType.SEA: " ",
    TerrainType.IMPASSABLE: "#",
}


TERRAIN_STYLES: dict[TerrainType, str] = {
    TerrainType.DESERT: "yellow",
    TerrainType.ROUGH: "yellow",
    TerrainType.ESCARPMENT: "bright_yellow",
    TerrainType.MOUNTAIN: "bright_yellow",
    TerrainType.SALT_MARSH: "blue",
    TerrainType.DEPRESSION: "dim yellow",
    TerrainType.OASIS: "green",
    TerrainType.TOWN: "white",
    TerrainType.CITY: "bold white",
    TerrainType.PORT: "bold blue",
    TerrainType.SEA: "blue",
    TerrainType.IMPASSABLE: "dim",
}


COHESION_STYLES: dict[str, str] = {
    CohesionLevel.ORGANIZED.value: "green",
    CohesionLevel.DISORGANIZED.value: "yellow",
    CohesionLevel.SHATTERED.value: "red",
}


def side_label(side: Optional[Side]) -> Text:
    if side is None:
        return Text("—", style="dim")
    style = SIDE_STYLES.get(side, "")
    return Text(side.value.capitalize(), style=style)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------


def render_header(view: GameView) -> Panel:
    """Top bar: turn, stage, phase, active side, weather, initiative."""
    state = view.state
    initiative_holder = next(
        (s for s, p in state.players.items() if p.has_initiative), None
    )

    stage_label = state.operations_stage.name.title()
    phase_label = state.phase.value.replace("_", " ").title()

    left = Text()
    left.append(f"Turn {state.game_turn}", style="bold")
    left.append(" · ")
    left.append(f"Stage {stage_label}")
    left.append(" · ")
    left.append(phase_label, style="bold magenta")

    mid = Text()
    mid.append("Active: ")
    mid.append_text(side_label(state.active_side))

    right = Text()
    right.append("Weather: ")
    right.append(state.weather.value.capitalize(), style=_weather_style(state.weather))
    right.append("   Initiative: ")
    right.append_text(side_label(initiative_holder))
    right.append("   Viewer: ")
    right.append_text(side_label(view.viewer))

    table = Table.grid(expand=True)
    table.add_column(justify="left", ratio=2)
    table.add_column(justify="center", ratio=1)
    table.add_column(justify="right", ratio=2)
    table.add_row(left, mid, right)
    return Panel(table, border_style="bright_blue", padding=(0, 1))


def _weather_style(w: WeatherState) -> str:
    return {
        WeatherState.CLEAR: "green",
        WeatherState.OVERCAST: "white",
        WeatherState.RAIN: "blue",
        WeatherState.SANDSTORM: "red",
    }.get(w, "")


# ---------------------------------------------------------------------------
# OOB panel
# ---------------------------------------------------------------------------


def render_oob(view: GameView, side: Side) -> Panel:
    """Order-of-battle panel for one side.

    Friendly OOB (side == view.viewer) shows full TOE / morale / status.
    Enemy OOB shows only the count of on-map units (Case 3.6).
    """
    is_enemy = side != view.viewer
    title = f"{side.value.capitalize()} OOB"
    if is_enemy:
        title += " (redacted)"

    units = [u for u in view.units if u.side == side]
    if is_enemy:
        on_map = [u for u in units if u.position is not None]
        body: RenderableType
        if not on_map:
            body = Text("No known enemy units on map.", style="dim")
        else:
            hex_counts: dict[HexCoord, int] = {}
            for u in on_map:
                if u.position is not None:
                    hex_counts[u.position] = hex_counts.get(u.position, 0) + 1
            tbl = Table(show_header=True, header_style="dim", expand=True, pad_edge=False)
            tbl.add_column("Hex", no_wrap=True)
            tbl.add_column("Stack", justify="right")
            for coord, count in sorted(hex_counts.items(), key=lambda kv: (kv[0].q, kv[0].r)):
                tbl.add_row(f"({coord.q},{coord.r})", str(count))
            body = tbl
        return Panel(body, title=title, border_style=SIDE_STYLES[side])

    tbl = Table(show_header=True, header_style="bold", expand=True, pad_edge=False)
    tbl.add_column("Unit", no_wrap=True)
    tbl.add_column("TOE", justify="right")
    tbl.add_column("Mor", justify="right")
    tbl.add_column("Coh", no_wrap=True)
    tbl.add_column("Flags", no_wrap=True)
    tbl.add_column("Hex", no_wrap=True)

    for u in sorted(units, key=lambda x: x.name or x.id):
        flags = _unit_flags(u)
        hex_str = f"({u.position.q},{u.position.r})" if u.position is not None else "—"
        toe_str = f"{u.current_toe}/{u.max_toe}" if u.max_toe else "—"
        mor_str = f"{u.current_morale:+d}" if u.current_morale is not None else "—"
        coh = u.cohesion or ""
        coh_txt = Text(coh[:3].upper(), style=COHESION_STYLES.get(coh, ""))
        tbl.add_row(
            u.name or u.id,
            toe_str,
            mor_str,
            coh_txt,
            flags,
            hex_str,
        )
    if not units:
        return Panel(Text("No units.", style="dim"), title=title, border_style=SIDE_STYLES[side])
    return Panel(tbl, title=title, border_style=SIDE_STYLES[side])


def _unit_flags(u: UnitView) -> Text:
    parts: list[tuple[str, str]] = []
    if u.reserve_status == ReserveStatus.RESERVE_I.value:
        parts.append(("R1", "cyan"))
    elif u.reserve_status == ReserveStatus.RESERVE_II.value:
        parts.append(("R2", "cyan"))
    if u.pinned:
        parts.append(("PIN", "red"))
    if u.broken_down:
        parts.append(("BRK", "yellow"))
    txt = Text()
    for i, (s, style) in enumerate(parts):
        if i:
            txt.append(" ")
        txt.append(s, style=style)
    if not parts:
        txt.append("—", style="dim")
    return txt


# ---------------------------------------------------------------------------
# Selected-hex panel
# ---------------------------------------------------------------------------


def render_hex_panel(view: GameView, coord: Optional[HexCoord]) -> Panel:
    """Details of the currently selected hex. coord=None → placeholder."""
    if coord is None:
        return Panel(Text("(no hex selected)", style="dim"), title="Hex", border_style="white")

    hv = view.hex_at(coord)
    if hv is None:
        return Panel(
            Text(f"No hex at ({coord.q},{coord.r})", style="red"),
            title="Hex",
            border_style="red",
        )

    mh = hv.hex
    header = Text()
    header.append(f"({coord.q},{coord.r}) ", style="bold")
    if mh.name:
        header.append(mh.name + " · ", style="bold")
    header.append(mh.terrain.value.replace("_", " ").title(),
                  style=TERRAIN_STYLES.get(mh.terrain, ""))
    if mh.port_capacity:
        header.append(f"  Port({mh.port_capacity})", style="bold blue")
    if mh.has_airfield:
        header.append("  Airfield", style="bold")
    elif mh.has_landing_strip:
        header.append("  LandingStrip", style="dim")

    controller = Text("Controller: ")
    controller.append_text(side_label(mh.controller))

    stack_lines = _render_stack(hv)

    body = Group(header, controller, Text(""), stack_lines)
    return Panel(body, title="Selected Hex", border_style="white")


def _render_stack(hv: HexView) -> RenderableType:
    if hv.stack_count == 0:
        return Text("Empty", style="dim")
    lines: list[Text] = []
    for u in hv.units:
        if u.is_friendly:
            t = Text()
            t.append("• ", style=SIDE_STYLES.get(u.side, ""))
            t.append(u.name or u.id)
            t.append("  ")
            if u.max_toe:
                t.append(f"TOE {u.current_toe}/{u.max_toe}")
            if u.current_morale is not None:
                t.append(f"  Mor {u.current_morale:+d}")
            if u.cohesion:
                t.append(f"  {u.cohesion[:3].upper()}",
                         style=COHESION_STYLES.get(u.cohesion, ""))
            lines.append(t)
        else:
            t = Text()
            t.append("• ", style=SIDE_STYLES.get(u.side, ""))
            t.append(f"Enemy unit ({u.side.value})", style="dim")
            lines.append(t)
    return Group(*lines)


# ---------------------------------------------------------------------------
# Map panel
# ---------------------------------------------------------------------------


@dataclass
class MapRenderOptions:
    """Tuning knobs for render_map()."""

    width: Optional[int] = None  # Columns of hex cells; None = auto-fit.
    height: Optional[int] = None  # Rows of hex cells; None = auto-fit.
    selected: Optional[HexCoord] = None


def render_map(view: GameView, opts: Optional[MapRenderOptions] = None) -> Panel:
    """Render an ASCII map of the known hexes.

    Each hex is shown as a single glyph (terrain), overlaid with a side
    letter (A/C) if a unit is stacked there. The selected hex is inverted.

    This is an intentionally simple flat-grid projection — good enough for
    the dashboard skeleton; a proper offset-hex rendering comes later.
    """
    opts = opts or MapRenderOptions()
    if not view.hexes:
        return Panel(Text("(map is empty)", style="dim"), title="Map", border_style="green")

    qs = [c.q for c in view.hexes]
    rs = [c.r for c in view.hexes]
    q_min, q_max = min(qs), max(qs)
    r_min, r_max = min(rs), max(rs)

    table = Table.grid()
    for _ in range(q_max - q_min + 1):
        table.add_column(no_wrap=True)

    for r in range(r_min, r_max + 1):
        # Offset rows for a flat-topped look.
        row_cells: list[Text] = []
        if (r - r_min) % 2 == 1:
            row_cells.append(Text(" "))
        for q in range(q_min, q_max + 1):
            coord = HexCoord(q, r)
            row_cells.append(_render_cell(view, coord, opts.selected))
        table.add_row(*row_cells)

    return Panel(table, title="Map", border_style="green")


def _render_cell(view: GameView, coord: HexCoord, selected: Optional[HexCoord]) -> Text:
    hv = view.hex_at(coord)
    if hv is None:
        return Text(" ", style="dim")

    glyph = TERRAIN_GLYPHS.get(hv.hex.terrain, "?")
    style = TERRAIN_STYLES.get(hv.hex.terrain, "")

    # Unit overlay: if any friendly unit here, use friendly-side letter.
    # Otherwise if enemy units present, use enemy letter (dim).
    friendly = hv.friendly_units()
    enemy = hv.enemy_units()
    if friendly:
        glyph = _side_letter(friendly[0].side)
        style = SIDE_STYLES.get(friendly[0].side, "")
    elif enemy:
        glyph = _side_letter(enemy[0].side).lower()
        style = SIDE_STYLES.get(enemy[0].side, "") + " dim"

    if selected is not None and coord == selected:
        style = (style + " reverse").strip()

    return Text(glyph, style=style)


def _side_letter(side: Side) -> str:
    return {Side.AXIS: "A", Side.COMMONWEALTH: "C"}.get(side, "?")


# ---------------------------------------------------------------------------
# Phase log panel
# ---------------------------------------------------------------------------


def render_log(view: GameView, n: int = 10) -> Panel:
    """Tail of the turn_log for the viewer."""
    tail = view.log[-n:] if n > 0 else []
    if not tail:
        return Panel(Text("(no events yet)", style="dim"), title="Phase Log",
                     border_style="bright_black")
    lines = [_format_log_line(e) for e in tail]
    return Panel(Group(*lines), title="Phase Log", border_style="bright_black")


def _format_log_line(e: LogEntry) -> Text:
    stage_tag = e.stage.name[0] if e.stage is not None else "-"
    phase_tag = _phase_short(e.phase)
    side_tag = e.side.value[:2].upper() if e.side is not None else "--"

    t = Text()
    t.append(f"[T{e.turn}.{stage_tag}.{phase_tag}] ", style="bright_black")
    t.append(side_tag + " ", style=SIDE_STYLES.get(e.side, "") if e.side else "dim")
    if e.category:
        t.append(f"({e.category}) ", style="cyan")
    t.append(e.message)
    return t


def _phase_short(phase: Phase) -> str:
    # 3-letter tag, best effort.
    words = phase.value.split("_")
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words).upper()[:4]


# ---------------------------------------------------------------------------
# Commands hint
# ---------------------------------------------------------------------------


def render_commands(hints: Optional[Iterable[tuple[str, str]]] = None) -> Panel:
    """One-line command shortcut reference.

    *hints* is a list of (key, label) pairs. Defaults are provided for a
    "read-only tour" of the dashboard; the real app overrides these.
    """
    if hints is None:
        hints = [
            ("n", "next phase"),
            ("arrows", "select hex"),
            ("s", "save"),
            ("l", "load"),
            ("q", "quit"),
        ]
    t = Text()
    for i, (key, label) in enumerate(hints):
        if i:
            t.append("  ")
        t.append(f"[{key}] ", style="bold green")
        t.append(label, style="white")
    return Panel(t, border_style="bright_black", padding=(0, 1))


# ---------------------------------------------------------------------------
# Composite layout
# ---------------------------------------------------------------------------


def build_layout(view: GameView, *, selected: Optional[HexCoord] = None) -> Layout:
    """Compose the full dashboard Layout from a GameView.

    Use layout.print() via a rich.Console to render once, or feed into a
    rich.live.Live for continuous refresh.
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=8),
    )

    layout["header"].update(render_header(view))

    body = layout["body"]
    body.split_row(
        Layout(name="map", ratio=3),
        Layout(name="center", ratio=2),
        Layout(name="oob", ratio=3),
    )
    body["map"].update(render_map(view, MapRenderOptions(selected=selected)))
    body["center"].update(render_hex_panel(view, selected))

    oob_col = body["oob"]
    oob_col.split_column(
        Layout(name="friendly"),
        Layout(name="enemy"),
    )
    oob_col["friendly"].update(render_oob(view, view.viewer))
    enemy_side = Side.COMMONWEALTH if view.viewer == Side.AXIS else Side.AXIS
    oob_col["enemy"].update(render_oob(view, enemy_side))

    footer = layout["footer"]
    footer.split_column(
        Layout(name="log", ratio=3),
        Layout(name="cmd", size=3),
    )
    footer["log"].update(render_log(view, n=8))
    footer["cmd"].update(render_commands())

    return layout


def render_dashboard(view: GameView, *, selected: Optional[HexCoord] = None) -> RenderableType:
    """Return a single Rich renderable for one-shot dashboard prints.

    Convenience wrapper around build_layout() for contexts (scripts, tests)
    that just want a renderable.
    """
    return build_layout(view, selected=selected)
