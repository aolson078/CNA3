"""Tests for cna.rules.stacking (Section 9.0)."""

from __future__ import annotations

from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    OrgSize,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
)
from cna.rules.stacking import (
    MAX_ZERO_SP_UNITS,
    available_stacking,
    check_hex_stacking,
    current_stacking,
    hex_stacking_limit,
    stacking_points,
    would_violate_stacking,
)


def _mk_unit(uid: str, org: OrgSize = OrgSize.BATTALION, ut: UnitType = UnitType.INFANTRY,
              at: HexCoord = HexCoord(0, 0), **kw) -> Unit:
    return Unit(id=uid, side=Side.AXIS, name=uid, unit_type=ut,
                unit_class=UnitClass.INFANTRY, org_size=org,
                stats=UnitStats(max_toe_strength=6), position=at, current_toe=6, **kw)


def _mk_state(terrain: TerrainType = TerrainType.DESERT) -> GameState:
    gs = GameState()
    gs.map = {HexCoord(0, 0): MapHex(coord=HexCoord(0, 0), terrain=terrain)}
    return gs


def test_sp_by_org_size():
    """Case 9.4 — stacking points by org size."""
    assert stacking_points(_mk_unit("d", OrgSize.DIVISION)) == 5
    assert stacking_points(_mk_unit("b", OrgSize.BRIGADE)) == 3
    assert stacking_points(_mk_unit("bn", OrgSize.BATTALION)) == 1
    assert stacking_points(_mk_unit("c", OrgSize.COMPANY)) == 0


def test_sp_hq_no_attached():
    """Case 9.12 — empty HQ = 0 SP."""
    hq = _mk_unit("hq", OrgSize.DIVISION, ut=UnitType.HEADQUARTERS)
    assert stacking_points(hq) == 0


def test_sp_hq_with_attached():
    """Case 9.12 — HQ with attached units uses printed SP."""
    hq = _mk_unit("hq", OrgSize.DIVISION, ut=UnitType.HEADQUARTERS,
                   attached_unit_ids=["sub1"])
    assert stacking_points(hq) == 5


def test_sp_truck():
    """Case 9.29 — trucks don't count."""
    t = _mk_unit("t", OrgSize.BATTALION, ut=UnitType.TRUCK)
    assert stacking_points(t) == 0


def test_hex_limit_desert():
    assert hex_stacking_limit(TerrainType.DESERT) == 10


def test_hex_limit_city():
    assert hex_stacking_limit(TerrainType.CITY) == 15


def test_current_stacking():
    gs = _mk_state()
    gs.units["a"] = _mk_unit("a", OrgSize.BRIGADE)
    gs.units["b"] = _mk_unit("b", OrgSize.BATTALION)
    assert current_stacking(gs, HexCoord(0, 0)) == 4  # 3 + 1


def test_would_violate_within_limit():
    gs = _mk_state()
    u = _mk_unit("u", OrgSize.BRIGADE)
    assert not would_violate_stacking(gs, HexCoord(0, 0), u)


def test_would_violate_exceeds_limit():
    gs = _mk_state(TerrainType.MOUNTAIN)  # limit 5
    gs.units["a"] = _mk_unit("a", OrgSize.BRIGADE)  # 3 SP
    gs.units["b"] = _mk_unit("b", OrgSize.BRIGADE)  # 3 SP = 6 total so far
    u = _mk_unit("u", OrgSize.BATTALION)  # +1 = 7 > 5 → violates
    # Already at 6 which exceeds 5, so any addition violates.
    assert would_violate_stacking(gs, HexCoord(0, 0), u)


def test_zero_sp_limit():
    """Case 9.25 — max 5 zero-SP units in non-city hex."""
    gs = _mk_state()
    for i in range(MAX_ZERO_SP_UNITS):
        gs.units[f"c{i}"] = _mk_unit(f"c{i}", OrgSize.COMPANY)
    new = _mk_unit("extra", OrgSize.COMPANY)
    assert would_violate_stacking(gs, HexCoord(0, 0), new)


def test_zero_sp_unlimited_in_city():
    gs = _mk_state(TerrainType.CITY)
    for i in range(10):
        gs.units[f"c{i}"] = _mk_unit(f"c{i}", OrgSize.COMPANY)
    new = _mk_unit("extra", OrgSize.COMPANY)
    assert not would_violate_stacking(gs, HexCoord(0, 0), new)


def test_check_hex_stacking_ok():
    gs = _mk_state()
    gs.units["a"] = _mk_unit("a", OrgSize.BATTALION)
    assert check_hex_stacking(gs, HexCoord(0, 0)) == []


def test_check_hex_stacking_violation():
    gs = _mk_state(TerrainType.MOUNTAIN)
    for i in range(3):
        gs.units[f"d{i}"] = _mk_unit(f"d{i}", OrgSize.DIVISION)
    errors = check_hex_stacking(gs, HexCoord(0, 0))
    assert len(errors) >= 1


def test_available_stacking():
    gs = _mk_state()
    gs.units["a"] = _mk_unit("a", OrgSize.BRIGADE)  # 3 SP
    assert available_stacking(gs, HexCoord(0, 0)) == 7  # 10 - 3
