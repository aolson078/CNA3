"""Tests for cna.rules.land_movement (Section 8.0)."""

from __future__ import annotations

import pytest

from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    OrgSize,
    Player,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
)
from cna.rules.capability_points import cohesion_value, spend_cp
from cna.rules.land_movement import (
    MoveResult,
    can_enter,
    is_motorized,
    move_unit,
    terrain_cp_cost,
    validate_move,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_unit(uid: str = "u1", side: Side = Side.AXIS, cpa: int = 20,
             unit_type: UnitType = UnitType.INFANTRY,
             at: HexCoord = HexCoord(0, 0), **kw) -> Unit:
    return Unit(
        id=uid, side=side, name=uid,
        unit_type=unit_type, unit_class=UnitClass.INFANTRY, org_size=OrgSize.BATTALION,
        stats=UnitStats(capability_point_allowance=cpa, max_toe_strength=6),
        position=at, current_toe=6, **kw,
    )


def _mk_line_map(n: int = 5, terrain: TerrainType = TerrainType.DESERT) -> dict[HexCoord, MapHex]:
    """A straight line of hexes from (0,0) to (n-1,0)."""
    return {
        HexCoord(q, 0): MapHex(coord=HexCoord(q, 0), terrain=terrain)
        for q in range(n)
    }


def _mk_state(hexes: dict[HexCoord, MapHex] | None = None,
              units: list[Unit] | None = None) -> GameState:
    gs = GameState()
    gs.map = hexes or _mk_line_map()
    gs.players = {
        Side.AXIS: Player(side=Side.AXIS),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH),
    }
    if units:
        for u in units:
            gs.units[u.id] = u
    return gs


# ---------------------------------------------------------------------------
# is_motorized (Case 8.91)
# ---------------------------------------------------------------------------


def test_tank_is_motorized():
    u = _mk_unit(unit_type=UnitType.TANK)
    assert is_motorized(u)


def test_infantry_not_motorized():
    u = _mk_unit(unit_type=UnitType.INFANTRY)
    assert not is_motorized(u)


def test_infantry_with_flag_is_motorized():
    u = _mk_unit(unit_type=UnitType.INFANTRY, is_motorized=True)
    assert is_motorized(u)


# ---------------------------------------------------------------------------
# terrain_cp_cost (Cases 8.31, 8.33, 8.46)
# ---------------------------------------------------------------------------


def test_desert_cost_infantry():
    u = _mk_unit(unit_type=UnitType.INFANTRY)
    assert terrain_cp_cost(TerrainType.DESERT, u) == 2


def test_town_cost():
    u = _mk_unit()
    assert terrain_cp_cost(TerrainType.TOWN, u) == 1


def test_road_overrides_terrain():
    u = _mk_unit()
    assert terrain_cp_cost(TerrainType.DESERT, u, on_road=True) == 1


def test_track_halves_cost():
    u = _mk_unit()
    base = terrain_cp_cost(TerrainType.DESERT, u)
    tracked = terrain_cp_cost(TerrainType.DESERT, u, on_track=True)
    assert tracked == max(1, base // 2)


def test_mountain_prohibited_for_motorized():
    u = _mk_unit(unit_type=UnitType.TANK)
    assert terrain_cp_cost(TerrainType.MOUNTAIN, u) == -1
    assert not can_enter(TerrainType.MOUNTAIN, u)


def test_mountain_allowed_for_infantry():
    u = _mk_unit(unit_type=UnitType.INFANTRY)
    cost = terrain_cp_cost(TerrainType.MOUNTAIN, u)
    assert cost > 0
    assert can_enter(TerrainType.MOUNTAIN, u)


def test_road_allows_prohibited_terrain():
    # Case 8.33: road negates terrain prohibition.
    u = _mk_unit(unit_type=UnitType.TANK)
    assert can_enter(TerrainType.MOUNTAIN, u, on_road=True)
    assert terrain_cp_cost(TerrainType.MOUNTAIN, u, on_road=True) == 1


def test_sea_always_prohibited():
    u = _mk_unit()
    assert not can_enter(TerrainType.SEA, u)
    assert not can_enter(TerrainType.SEA, u, on_road=True)


# ---------------------------------------------------------------------------
# validate_move (Cases 8.13, 8.32)
# ---------------------------------------------------------------------------


def test_validate_legal_path():
    u = _mk_unit(at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    path = [HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0)]
    errors = validate_move(gs, u, path)
    assert errors == []


def test_validate_wrong_start():
    u = _mk_unit(at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    path = [HexCoord(1, 0), HexCoord(2, 0)]
    errors = validate_move(gs, u, path)
    assert any("start" in e.lower() for e in errors)


def test_validate_non_adjacent():
    u = _mk_unit(at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    path = [HexCoord(0, 0), HexCoord(3, 0)]  # Skip hexes.
    errors = validate_move(gs, u, path)
    assert any("adjacent" in e.lower() for e in errors)


def test_validate_enemy_occupied():
    u = _mk_unit(at=HexCoord(0, 0), side=Side.AXIS)
    enemy = _mk_unit(uid="e1", at=HexCoord(1, 0), side=Side.COMMONWEALTH)
    gs = _mk_state(units=[u, enemy])
    path = [HexCoord(0, 0), HexCoord(1, 0)]
    errors = validate_move(gs, u, path)
    assert any("enemy" in e.lower() for e in errors)


def test_validate_off_map():
    u = _mk_unit(at=HexCoord(0, 0))
    gs = _mk_state(hexes=_mk_line_map(2), units=[u])
    path = [HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0)]  # 2,0 not on map.
    errors = validate_move(gs, u, path)
    assert any("off-map" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# move_unit (Cases 8.11-8.16)
# ---------------------------------------------------------------------------


def test_basic_move():
    u = _mk_unit(cpa=20, at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    path = [HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0)]
    result = move_unit(gs, "u1", path)
    assert u.position == HexCoord(2, 0)
    assert result.cp_spent == 4  # 2 desert hexes × 2 CP each
    assert result.dp_earned == 0


def test_move_spends_cp():
    u = _mk_unit(cpa=10, at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    move_unit(gs, "u1", [HexCoord(0, 0), HexCoord(1, 0)])
    assert u.capability_points_spent == 2


def test_move_exceeds_cpa_earns_dp():
    u = _mk_unit(cpa=3, at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    # 2 desert hexes = 4 CP, exceeds CPA of 3 by 1.
    result = move_unit(gs, "u1", [HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0)])
    assert result.dp_earned == 1
    assert cohesion_value(u) == -1


def test_move_stops_at_voluntary_cap():
    # Non-motorized (CPA 8) → voluntary cap 12. Desert costs 2 per hex.
    # After 6 hexes = 12 CP → should stop.
    hexes = _mk_line_map(10)
    u = _mk_unit(cpa=8, at=HexCoord(0, 0))
    gs = _mk_state(hexes=hexes, units=[u])
    path = [HexCoord(q, 0) for q in range(8)]
    result = move_unit(gs, "u1", path)
    # Should stop after spending 12 CP (6 hexes entered).
    assert result.cp_spent == 12
    assert u.position == HexCoord(6, 0)


def test_move_stops_at_enemy_zoc():
    # Place an enemy 1 hex away from the destination.
    u = _mk_unit(cpa=20, at=HexCoord(0, 0), side=Side.AXIS)
    enemy = _mk_unit(uid="e1", cpa=20, at=HexCoord(3, 0), side=Side.COMMONWEALTH)
    gs = _mk_state(hexes=_mk_line_map(5), units=[u, enemy])

    # Try to move through (2,0) which is adjacent to enemy at (3,0).
    path = [HexCoord(0, 0), HexCoord(1, 0), HexCoord(2, 0)]
    result = move_unit(gs, "u1", path)
    assert result.stopped_by_zoc is True
    assert u.position == HexCoord(2, 0)


def test_move_into_prohibited_terrain_raises():
    hexes = {
        HexCoord(0, 0): MapHex(coord=HexCoord(0, 0), terrain=TerrainType.DESERT),
        HexCoord(1, 0): MapHex(coord=HexCoord(1, 0), terrain=TerrainType.SEA),
    }
    u = _mk_unit(cpa=20, at=HexCoord(0, 0))
    gs = _mk_state(hexes=hexes, units=[u])
    with pytest.raises(RuleViolationError):
        move_unit(gs, "u1", [HexCoord(0, 0), HexCoord(1, 0)])


def test_move_nonexistent_unit_raises():
    gs = _mk_state()
    with pytest.raises(RuleViolationError):
        move_unit(gs, "nonexistent", [HexCoord(0, 0)])


def test_move_empty_path_is_noop():
    u = _mk_unit(at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    result = move_unit(gs, "u1", [])
    assert result.cp_spent == 0
    assert u.position == HexCoord(0, 0)


def test_move_with_road():
    h0 = HexCoord(0, 0)
    h1 = HexCoord(1, 0)
    h2 = HexCoord(2, 0)
    hexes = {
        h0: MapHex(coord=h0, terrain=TerrainType.DESERT, road_exits=frozenset({h1})),
        h1: MapHex(coord=h1, terrain=TerrainType.DESERT,
                   road_exits=frozenset({h0, h2})),
        h2: MapHex(coord=h2, terrain=TerrainType.DESERT, road_exits=frozenset({h1})),
    }
    u = _mk_unit(cpa=20, at=h0)
    gs = _mk_state(hexes=hexes, units=[u])
    result = move_unit(gs, "u1", [h0, h1, h2])
    assert result.cp_spent == 2  # 2 road hexes × 1 CP each.


def test_involuntary_move_bypasses_cap():
    # Non-motorized CPA 8 → voluntary cap 12. But involuntary bypasses.
    hexes = _mk_line_map(10)
    u = _mk_unit(cpa=8, at=HexCoord(0, 0))
    gs = _mk_state(hexes=hexes, units=[u])
    path = [HexCoord(q, 0) for q in range(8)]
    result = move_unit(gs, "u1", path, voluntary=False)
    assert result.cp_spent == 14  # 7 desert hexes × 2 CP
    assert u.position == HexCoord(7, 0)


def test_move_logs_result():
    u = _mk_unit(cpa=20, at=HexCoord(0, 0))
    gs = _mk_state(units=[u])
    result = move_unit(gs, "u1", [HexCoord(0, 0), HexCoord(1, 0)])
    assert result.unit_id == "u1"
    assert len(result.path) == 2
