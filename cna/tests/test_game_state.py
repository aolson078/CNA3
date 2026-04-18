"""Smoke tests for cna.engine.game_state dataclasses."""

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


def _infantry_battalion(unit_id: str, side: Side, at: HexCoord | None = None) -> Unit:
    return Unit(
        id=unit_id,
        side=side,
        name=unit_id,
        unit_type=UnitType.INFANTRY,
        unit_class=UnitClass.INFANTRY,
        org_size=OrgSize.BATTALION,
        stats=UnitStats(capability_point_allowance=8, basic_morale=1, max_toe_strength=6),
        position=at,
        current_toe=6,
        current_morale=1,
    )


def test_gamestate_defaults():
    gs = GameState()
    assert gs.schema_version == GameState.SCHEMA_VERSION
    assert gs.game_turn == 1
    assert gs.phase == Phase.INITIATIVE_DETERMINATION
    assert gs.players == {}
    assert gs.units == {}
    assert gs.map == {}


def test_units_on_side_filters_correctly():
    gs = GameState()
    a = _infantry_battalion("ax1", Side.AXIS)
    b = _infantry_battalion("cw1", Side.COMMONWEALTH)
    gs.units = {a.id: a, b.id: b}
    assert gs.units_on_side(Side.AXIS) == [a]
    assert gs.units_on_side(Side.COMMONWEALTH) == [b]


def test_units_at_hex():
    gs = GameState()
    h = HexCoord(3, 4)
    a = _infantry_battalion("ax1", Side.AXIS, at=h)
    b = _infantry_battalion("ax2", Side.AXIS, at=h)
    c = _infantry_battalion("ax3", Side.AXIS, at=HexCoord(0, 0))
    gs.units = {u.id: u for u in (a, b, c)}
    stack = gs.units_at(h)
    assert set(u.id for u in stack) == {"ax1", "ax2"}


def test_enemy_returns_opposite():
    gs = GameState()
    assert gs.enemy(Side.AXIS) == Side.COMMONWEALTH
    assert gs.enemy(Side.COMMONWEALTH) == Side.AXIS


def test_unit_is_combat_unit():
    infantry = _infantry_battalion("i1", Side.AXIS)
    assert infantry.is_combat_unit()

    truck = Unit(
        id="t1", side=Side.AXIS, name="Truck", unit_type=UnitType.TRUCK,
        unit_class=UnitClass.TRUCK, org_size=OrgSize.COMPANY,
    )
    assert not truck.is_combat_unit()

    empty_hq = Unit(
        id="hq1", side=Side.AXIS, name="HQ", unit_type=UnitType.HEADQUARTERS,
        unit_class=UnitClass.INFANTRY, org_size=OrgSize.DIVISION,
    )
    assert not empty_hq.is_combat_unit()

    staffed_hq = Unit(
        id="hq2", side=Side.AXIS, name="HQ", unit_type=UnitType.HEADQUARTERS,
        unit_class=UnitClass.INFANTRY, org_size=OrgSize.DIVISION,
        attached_unit_ids=["sub1"],
    )
    assert staffed_hq.is_combat_unit()


def test_unit_remaining_cp():
    u = _infantry_battalion("ax1", Side.AXIS)
    assert u.remaining_cp() == 8
    u.capability_points_spent = 3
    assert u.remaining_cp() == 5
    u.capability_points_spent = 99
    assert u.remaining_cp() == 0


def test_player_accessor():
    gs = GameState()
    gs.players[Side.AXIS] = Player(side=Side.AXIS, name="Rommel")
    assert gs.player(Side.AXIS).name == "Rommel"


def test_log_append():
    gs = GameState()
    gs.active_side = Side.AXIS
    e1 = gs.log("started turn")
    e2 = gs.log("rolled weather", category="weather", data={"result": 22})
    assert len(gs.turn_log) == 2
    assert e1.seq == 0 and e2.seq == 1
    assert e1.message == "started turn"
    assert e2.category == "weather"
    assert e2.data == {"result": 22}
    # Context auto-populated.
    assert e1.turn == gs.game_turn
    assert e1.phase == gs.phase
    assert e1.side == Side.AXIS


def test_log_side_override():
    gs = GameState()
    gs.active_side = Side.AXIS
    entry = gs.log("cw reacts", side=Side.COMMONWEALTH)
    assert entry.side == Side.COMMONWEALTH


def test_recent_log():
    gs = GameState()
    for i in range(5):
        gs.log(f"event {i}")
    tail = gs.recent_log(3)
    assert [e.message for e in tail] == ["event 2", "event 3", "event 4"]
    assert gs.recent_log(0) == []


def test_maphex_default_terrain_is_desert():
    h = MapHex(coord=HexCoord(0, 0))
    assert h.terrain == TerrainType.DESERT
