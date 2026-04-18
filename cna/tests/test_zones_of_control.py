"""Tests for cna.rules.zones_of_control (Section 10.0)."""

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
from cna.rules.capability_points import apply_disorganization
from cna.rules.zones_of_control import (
    can_enter_zoc,
    controlled_hexes,
    hex_exerts_zoc,
    is_enemy_zoc,
    must_stop_for_zoc,
    unit_exerts_zoc,
)


def _mk_unit(uid: str, side: Side, org: OrgSize = OrgSize.BRIGADE,
              at: HexCoord = HexCoord(0, 0), **kw) -> Unit:
    return Unit(id=uid, side=side, name=uid, unit_type=UnitType.INFANTRY,
                unit_class=UnitClass.INFANTRY, org_size=org,
                stats=UnitStats(capability_point_allowance=10, max_toe_strength=6),
                position=at, current_toe=6, **kw)


def _mk_3x3_map() -> dict[HexCoord, MapHex]:
    hexes = {}
    for q in range(-1, 2):
        for r in range(-1, 2):
            hexes[HexCoord(q, r)] = MapHex(coord=HexCoord(q, r), terrain=TerrainType.DESERT)
    return hexes


def _mk_state(units: list[Unit] | None = None) -> GameState:
    gs = GameState()
    gs.map = _mk_3x3_map()
    if units:
        for u in units:
            gs.units[u.id] = u
    return gs


# ---------------------------------------------------------------------------
# unit_exerts_zoc (Case 10.11)
# ---------------------------------------------------------------------------


def test_brigade_exerts_zoc():
    u = _mk_unit("b", Side.AXIS, OrgSize.BRIGADE)
    assert unit_exerts_zoc(u)


def test_battalion_does_not_exert_zoc_alone():
    """Case 10.11 — battalion (1 SP) does NOT exert ZoC individually."""
    u = _mk_unit("bn", Side.AXIS, OrgSize.BATTALION)
    assert not unit_exerts_zoc(u)


def test_truck_never_exerts():
    u = _mk_unit("t", Side.AXIS, OrgSize.BRIGADE)
    u.unit_type = UnitType.TRUCK
    assert not unit_exerts_zoc(u)


def test_empty_hq_no_zoc():
    hq = _mk_unit("hq", Side.AXIS, OrgSize.DIVISION)
    hq.unit_type = UnitType.HEADQUARTERS
    hq.attached_unit_ids = []
    assert not unit_exerts_zoc(hq)


def test_shattered_unit_no_zoc():
    """Case 10.14 — Shattered units do not exert ZoC."""
    u = _mk_unit("s", Side.AXIS, OrgSize.BRIGADE)
    apply_disorganization(u, 30)
    assert not unit_exerts_zoc(u)


# ---------------------------------------------------------------------------
# hex_exerts_zoc — combined SP (Case 10.11)
# ---------------------------------------------------------------------------


def test_hex_with_two_battalions_exerts_zoc():
    """Case 10.11 — multiple units summing >1 SP exert ZoC."""
    a = _mk_unit("a", Side.AXIS, OrgSize.BATTALION, at=HexCoord(0, 0))
    b = _mk_unit("b", Side.AXIS, OrgSize.BATTALION, at=HexCoord(0, 0))
    gs = _mk_state([a, b])
    assert hex_exerts_zoc(gs, HexCoord(0, 0), Side.AXIS)


def test_hex_with_one_battalion_no_zoc():
    a = _mk_unit("a", Side.AXIS, OrgSize.BATTALION, at=HexCoord(0, 0))
    gs = _mk_state([a])
    assert not hex_exerts_zoc(gs, HexCoord(0, 0), Side.AXIS)


# ---------------------------------------------------------------------------
# controlled_hexes (Case 10.21)
# ---------------------------------------------------------------------------


def test_controlled_hexes_returns_neighbors():
    u = _mk_unit("u", Side.AXIS, OrgSize.BRIGADE, at=HexCoord(0, 0))
    gs = _mk_state([u])
    ctrld = controlled_hexes(gs, HexCoord(0, 0), Side.AXIS)
    # Should include in-bounds neighbors that are desert (not blocked).
    assert len(ctrld) > 0
    assert all(isinstance(c, HexCoord) for c in ctrld)


def test_controlled_hexes_blocks_sea():
    gs = _mk_state()
    gs.map[HexCoord(1, 0)] = MapHex(coord=HexCoord(1, 0), terrain=TerrainType.SEA)
    u = _mk_unit("u", Side.AXIS, OrgSize.BRIGADE, at=HexCoord(0, 0))
    gs.units[u.id] = u
    ctrld = controlled_hexes(gs, HexCoord(0, 0), Side.AXIS)
    assert HexCoord(1, 0) not in ctrld


# ---------------------------------------------------------------------------
# is_enemy_zoc (Case 10.0)
# ---------------------------------------------------------------------------


def test_is_enemy_zoc_basic():
    enemy = _mk_unit("e", Side.COMMONWEALTH, OrgSize.BRIGADE, at=HexCoord(0, 0))
    gs = _mk_state([enemy])
    # Adjacent hex should be in enemy ZoC.
    assert is_enemy_zoc(gs, HexCoord(1, 0), Side.AXIS)


def test_friendly_negates_zoc():
    """Case 10.26 — Friendly combat unit negates enemy ZoC."""
    enemy = _mk_unit("e", Side.COMMONWEALTH, OrgSize.BRIGADE, at=HexCoord(0, 0))
    friend = _mk_unit("f", Side.AXIS, OrgSize.BATTALION, at=HexCoord(1, 0))
    gs = _mk_state([enemy, friend])
    assert not is_enemy_zoc(gs, HexCoord(1, 0), Side.AXIS)


# ---------------------------------------------------------------------------
# must_stop_for_zoc (Case 10.23)
# ---------------------------------------------------------------------------


def test_must_stop_in_enemy_zoc():
    enemy = _mk_unit("e", Side.COMMONWEALTH, OrgSize.BRIGADE, at=HexCoord(0, 0))
    mover = _mk_unit("m", Side.AXIS, at=HexCoord(-1, 0))
    gs = _mk_state([enemy, mover])
    assert must_stop_for_zoc(gs, HexCoord(1, 0), mover)


# ---------------------------------------------------------------------------
# can_enter_zoc (Cases 10.24, 10.29)
# ---------------------------------------------------------------------------


def test_cannot_move_zoc_to_zoc():
    """Case 10.24 — Cannot move from one enemy ZoC to another."""
    e1 = _mk_unit("e1", Side.COMMONWEALTH, OrgSize.BRIGADE, at=HexCoord(-1, 0))
    e2 = _mk_unit("e2", Side.COMMONWEALTH, OrgSize.BRIGADE, at=HexCoord(1, -1))
    mover = _mk_unit("m", Side.AXIS, OrgSize.BATTALION, at=HexCoord(0, -1))
    gs = _mk_state([e1, e2, mover])
    # Mover at (0,-1) adjacent to e1 at (-1,0). Its own presence normally
    # negates ZoC per 10.26, but can_enter_zoc excludes the mover when
    # checking if the origin hex is in enemy ZoC.
    # Target (0,0) is adjacent to both enemies → in enemy ZoC.
    assert not can_enter_zoc(gs, HexCoord(0, 0), mover)


def test_truck_blocked_from_zoc_without_escort():
    """Case 10.29 — Truck convoys need friendly combat escort in enemy ZoC."""
    enemy = _mk_unit("e", Side.COMMONWEALTH, OrgSize.BRIGADE, at=HexCoord(0, 0))
    truck = _mk_unit("t", Side.AXIS, OrgSize.BATTALION, at=HexCoord(-1, -1))
    truck.unit_type = UnitType.TRUCK
    gs = _mk_state([enemy, truck])
    assert not can_enter_zoc(gs, HexCoord(1, 0), truck)
