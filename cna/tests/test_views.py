"""Tests for cna.ui.views — limited-intelligence projection."""

from __future__ import annotations

from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    OrgSize,
    Phase,
    Player,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
)
from cna.ui.views import build_view, project_unit


def _mk_unit(uid: str, side: Side, at: HexCoord | None = None) -> Unit:
    return Unit(
        id=uid,
        side=side,
        name=uid,
        unit_type=UnitType.INFANTRY,
        unit_class=UnitClass.INFANTRY,
        org_size=OrgSize.BATTALION,
        stats=UnitStats(capability_point_allowance=8, basic_morale=1, max_toe_strength=6),
        position=at,
        current_toe=6,
        current_morale=1,
    )


def _populated_state() -> GameState:
    gs = GameState()
    gs.players = {
        Side.AXIS: Player(side=Side.AXIS, has_initiative=True),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH),
    }
    h = HexCoord(0, 0)
    gs.map = {h: MapHex(coord=h, terrain=TerrainType.TOWN, name="Tobruk")}
    gs.units = {
        "ax1": _mk_unit("ax1", Side.AXIS, at=h),
        "cw1": _mk_unit("cw1", Side.COMMONWEALTH, at=h),
    }
    return gs


def test_project_unit_friendly_full():
    gs = _populated_state()
    uv = project_unit(gs.units["ax1"], viewer=Side.AXIS)
    assert uv.is_friendly is True
    assert uv.name == "ax1"
    assert uv.current_toe == 6
    assert uv.max_toe == 6
    assert uv.capability_point_allowance == 8
    assert uv.is_opaque is False


def test_project_unit_enemy_opaque():
    gs = _populated_state()
    uv = project_unit(gs.units["cw1"], viewer=Side.AXIS)
    assert uv.is_friendly is False
    assert uv.name is None
    assert uv.current_toe is None
    assert uv.max_toe is None
    assert uv.cohesion is None
    # But position and side are visible (Case 3.62 "Map").
    assert uv.side == Side.COMMONWEALTH
    assert uv.position == HexCoord(0, 0)
    assert uv.is_opaque is True


def test_build_view_groups_units_by_hex():
    gs = _populated_state()
    view = build_view(gs, viewer=Side.AXIS)
    hv = view.hex_at(HexCoord(0, 0))
    assert hv is not None
    assert hv.stack_count == 2
    assert len(hv.friendly_units()) == 1
    assert len(hv.enemy_units()) == 1


def test_build_view_friendly_vs_enemy_lists():
    gs = _populated_state()
    view = build_view(gs, viewer=Side.AXIS)
    assert [u.id for u in view.friendly_units()] == ["ax1"]
    assert [u.id for u in view.enemy_units()] == ["cw1"]


def test_build_view_redacts_enemy_log():
    gs = _populated_state()
    gs.active_side = Side.AXIS
    gs.log("axis moved panzer")  # friendly entry
    gs.active_side = Side.COMMONWEALTH
    gs.log("commonwealth barrage fired", category="combat",
           data={"target": "ax1"})
    view = build_view(gs, viewer=Side.AXIS)
    # Friendly entry passes through.
    axis_entry = view.log[0]
    assert axis_entry.message == "axis moved panzer"
    # Enemy entry is redacted.
    cw_entry = view.log[1]
    assert cw_entry.message == "(enemy action)"
    assert cw_entry.data == {}
    # Phase/turn still accurate so the dashboard can show "something happened".
    assert cw_entry.side == Side.COMMONWEALTH
    assert cw_entry.phase == gs.phase


def test_build_view_global_log_entries_visible_to_both():
    gs = _populated_state()
    gs.log("weather rolled", side=None, category="weather")
    axis_view = build_view(gs, viewer=Side.AXIS)
    cw_view = build_view(gs, viewer=Side.COMMONWEALTH)
    assert axis_view.log[0].message == "weather rolled"
    assert cw_view.log[0].message == "weather rolled"
