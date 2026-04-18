"""Tests for cna.ui.dashboard — Rich renderers.

These tests exercise the render functions with a Console that captures
output to a string. We don't do full snapshot comparisons (that's brittle
against Rich version changes); we check that key pieces of information
appear in the rendered output, and that no renderer raises.
"""

from __future__ import annotations

import io

from rich.console import Console

from cna.engine.game_state import (
    CohesionLevel,
    GameState,
    HexCoord,
    MapHex,
    OperationsStage,
    OrgSize,
    Phase,
    Player,
    ReserveStatus,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
    WeatherState,
)
from cna.ui.dashboard import (
    MapRenderOptions,
    build_layout,
    render_commands,
    render_header,
    render_hex_panel,
    render_log,
    render_map,
    render_oob,
)
from cna.ui.views import build_view


def _render(renderable, width: int = 120) -> str:
    buf = io.StringIO()
    console = Console(file=buf, width=width, force_terminal=False, color_system=None,
                      record=False, legacy_windows=False)
    console.print(renderable)
    return buf.getvalue()


def _make_view(viewer: Side = Side.AXIS):
    gs = GameState()
    gs.game_turn = 3
    gs.operations_stage = OperationsStage.SECOND
    gs.phase = Phase.MOVEMENT_AND_COMBAT
    gs.active_side = Side.AXIS
    gs.weather = WeatherState.SANDSTORM
    gs.players = {
        Side.AXIS: Player(side=Side.AXIS, name="Rommel", has_initiative=True),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH, name="O'Connor"),
    }
    h1 = HexCoord(0, 0)
    h2 = HexCoord(1, 0)
    gs.map = {
        h1: MapHex(coord=h1, terrain=TerrainType.TOWN, name="Tobruk", port_capacity=4,
                   controller=Side.COMMONWEALTH),
        h2: MapHex(coord=h2, terrain=TerrainType.DESERT),
    }
    gs.units["ax.21pz"] = Unit(
        id="ax.21pz", side=Side.AXIS, name="21st Panzer",
        unit_type=UnitType.TANK, unit_class=UnitClass.ARMOR, org_size=OrgSize.DIVISION,
        stats=UnitStats(capability_point_allowance=10, max_toe_strength=12),
        position=h2, current_toe=9, current_morale=2,
        cohesion=CohesionLevel.ORGANIZED, reserve_status=ReserveStatus.RESERVE_I,
    )
    gs.units["cw.7armd"] = Unit(
        id="cw.7armd", side=Side.COMMONWEALTH, name="7th Armoured",
        unit_type=UnitType.TANK, unit_class=UnitClass.ARMOR, org_size=OrgSize.DIVISION,
        stats=UnitStats(capability_point_allowance=10, max_toe_strength=12),
        position=h1, current_toe=10, current_morale=1, pinned=True,
    )
    gs.log("21st Panzer advances", category="movement")
    return gs, build_view(gs, viewer)


def test_header_shows_turn_and_phase():
    _, view = _make_view()
    out = _render(render_header(view))
    assert "Turn 3" in out
    assert "Second" in out
    assert "Movement And Combat" in out
    assert "Sandstorm" in out


def test_header_shows_viewer():
    _, view = _make_view(viewer=Side.COMMONWEALTH)
    out = _render(render_header(view))
    assert "Commonwealth" in out


def test_oob_friendly_shows_toe_and_name():
    _, view = _make_view(viewer=Side.AXIS)
    out = _render(render_oob(view, Side.AXIS))
    assert "21st Panzer" in out
    assert "9/12" in out  # TOE column
    assert "R1" in out  # reserve marker flag


def test_oob_enemy_is_redacted_for_viewer():
    _, view = _make_view(viewer=Side.AXIS)
    out = _render(render_oob(view, Side.COMMONWEALTH))
    # Name must NOT appear in redacted OOB (Case 3.6).
    assert "7th Armoured" not in out
    assert "redacted" in out.lower()
    # Stack count is allowed (map is public).
    assert "(0,0)" in out


def test_hex_panel_shows_selected_terrain_and_stack():
    _, view = _make_view(viewer=Side.COMMONWEALTH)
    out = _render(render_hex_panel(view, HexCoord(0, 0)))
    assert "Tobruk" in out
    assert "Town" in out
    assert "Port(4)" in out
    # Viewer is Commonwealth, so friendly unit is shown.
    assert "7th Armoured" in out


def test_hex_panel_enemy_unit_opaque():
    _, view = _make_view(viewer=Side.COMMONWEALTH)
    # h2 holds the Axis 21 Pz — from CW's POV should be opaque.
    out = _render(render_hex_panel(view, HexCoord(1, 0)))
    assert "21st Panzer" not in out
    assert "Enemy unit" in out


def test_hex_panel_nonexistent_hex():
    _, view = _make_view()
    out = _render(render_hex_panel(view, HexCoord(99, 99)))
    assert "No hex" in out


def test_hex_panel_no_selection():
    _, view = _make_view()
    out = _render(render_hex_panel(view, None))
    assert "no hex selected" in out.lower()


def test_render_map_does_not_raise():
    _, view = _make_view()
    out = _render(render_map(view, MapRenderOptions(selected=HexCoord(0, 0))))
    assert "Map" in out


def test_render_log_shows_entry():
    _, view = _make_view()
    out = _render(render_log(view, n=5))
    assert "21st Panzer advances" in out


def test_render_log_empty():
    gs = GameState()
    view = build_view(gs, viewer=Side.AXIS)
    out = _render(render_log(view))
    assert "no events" in out.lower()


def test_render_commands_defaults():
    out = _render(render_commands())
    assert "next phase" in out
    assert "quit" in out


def test_render_commands_custom():
    out = _render(render_commands([("x", "do thing")]))
    assert "do thing" in out
    assert "next phase" not in out


def test_build_layout_composes_all_panels():
    _, view = _make_view()
    layout = build_layout(view, selected=HexCoord(0, 0))
    # Each named region is present and renderable.
    out = _render(layout, width=160)
    # Spot-check pieces from each panel.
    assert "Turn 3" in out
    assert "Tobruk" in out
    assert "21st Panzer" in out  # friendly OOB
    assert "redacted" in out.lower()  # enemy OOB
    assert "next phase" in out  # commands
