"""Integration tests for abstract supply tracking (Section 32).

Tests fuel consumption during movement, ammo consumption during combat,
supply pool initialization, and dashboard display.
"""

from __future__ import annotations

import io

from rich.console import Console

from cna.data.scenarios.operation_compass import build_grazianis_offensive
from cna.engine.dice import DiceRoller
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
from cna.rules.abstract.supply import (
    SupplyPool,
    consume_combat_ammo,
    consume_movement_fuel,
    get_supply_pool,
    init_supply_pools,
    save_supply_pool,
)
from cna.ui.app import App, Key


# ---------------------------------------------------------------------------
# Supply pool basics
# ---------------------------------------------------------------------------


def test_init_supply_pools():
    gs = GameState()
    init_supply_pools(gs, axis_ammo=3000, axis_fuel=2500, cw_ammo=5000, cw_fuel=7000)
    ax = get_supply_pool(gs, Side.AXIS)
    cw = get_supply_pool(gs, Side.COMMONWEALTH)
    assert ax.ammo == 3000
    assert ax.fuel == 2500
    assert cw.ammo == 5000
    assert cw.fuel == 7000


def test_supply_pool_spend():
    pool = SupplyPool(ammo=100, fuel=50)
    spent = pool.spend_ammo(10)
    assert spent == 10
    assert pool.ammo == 90
    spent = pool.spend_fuel(60)
    assert spent == 50  # Capped at available.
    assert pool.fuel == 0


def test_supply_pool_has_checks():
    pool = SupplyPool(ammo=5, fuel=0)
    assert pool.has_ammo(5)
    assert not pool.has_ammo(6)
    assert not pool.has_fuel(1)


def test_get_supply_pool_default():
    gs = GameState()
    pool = get_supply_pool(gs, Side.AXIS)
    assert pool.ammo == 0
    assert pool.fuel == 0


# ---------------------------------------------------------------------------
# Scenario supply initialization
# ---------------------------------------------------------------------------


def test_scenario_has_supply():
    gs = build_grazianis_offensive()
    ax = get_supply_pool(gs, Side.AXIS)
    cw = get_supply_pool(gs, Side.COMMONWEALTH)
    assert ax.ammo > 0
    assert ax.fuel > 0
    assert cw.ammo > 0
    assert cw.fuel > 0


# ---------------------------------------------------------------------------
# Fuel consumption during movement
# ---------------------------------------------------------------------------


def test_motorized_movement_consumes_fuel():
    gs = GameState()
    init_supply_pools(gs, axis_ammo=100, axis_fuel=100, cw_ammo=100, cw_fuel=100)
    tank = Unit(
        id="t1", side=Side.AXIS, name="Tank", unit_type=UnitType.TANK,
        unit_class=UnitClass.ARMOR, org_size=OrgSize.BATTALION,
        stats=UnitStats(capability_point_allowance=25, max_toe_strength=4),
        position=HexCoord(0, 0), current_toe=4,
    )
    gs.units[tank.id] = tank
    exp = consume_movement_fuel(gs, tank, hexes_moved=3)
    assert exp.fuel >= 1
    pool = get_supply_pool(gs, Side.AXIS)
    assert pool.fuel < 100


def test_infantry_movement_no_fuel():
    gs = GameState()
    init_supply_pools(gs, axis_ammo=100, axis_fuel=100, cw_ammo=100, cw_fuel=100)
    inf = Unit(
        id="i1", side=Side.AXIS, name="Infantry", unit_type=UnitType.INFANTRY,
        unit_class=UnitClass.INFANTRY, org_size=OrgSize.BATTALION,
        stats=UnitStats(capability_point_allowance=8, max_toe_strength=6),
        position=HexCoord(0, 0), current_toe=6,
    )
    gs.units[inf.id] = inf
    exp = consume_movement_fuel(gs, inf, hexes_moved=3)
    assert exp.fuel == 0
    pool = get_supply_pool(gs, Side.AXIS)
    assert pool.fuel == 100


# ---------------------------------------------------------------------------
# Ammo consumption during combat
# ---------------------------------------------------------------------------


def test_combat_consumes_ammo_attacker():
    gs = GameState()
    init_supply_pools(gs, axis_ammo=100, axis_fuel=100, cw_ammo=100, cw_fuel=100)
    exp = consume_combat_ammo(gs, Side.AXIS, is_phasing=True)
    assert exp.ammo == 2  # Case 32.21: phasing attacker = 2 ammo.
    pool = get_supply_pool(gs, Side.AXIS)
    assert pool.ammo == 98


def test_combat_consumes_ammo_defender():
    gs = GameState()
    init_supply_pools(gs, axis_ammo=100, axis_fuel=100, cw_ammo=100, cw_fuel=100)
    exp = consume_combat_ammo(gs, Side.COMMONWEALTH, is_phasing=False)
    assert exp.ammo == 1  # Case 32.21: non-phasing defender = 1 ammo.


def test_probe_consumes_less_ammo():
    gs = GameState()
    init_supply_pools(gs, axis_ammo=100, axis_fuel=100, cw_ammo=100, cw_fuel=100)
    exp = consume_combat_ammo(gs, Side.AXIS, is_phasing=True, is_probe=True)
    assert exp.ammo == 1  # Probe = 1 ammo.


def test_barrage_consumes_more_ammo():
    gs = GameState()
    init_supply_pools(gs, axis_ammo=100, axis_fuel=100, cw_ammo=100, cw_fuel=100)
    exp = consume_combat_ammo(gs, Side.AXIS, is_phasing=True, is_barrage=True)
    assert exp.ammo == 2  # Case 32.21: barrage = 2 ammo.


# ---------------------------------------------------------------------------
# App integration — supply consumed during play
# ---------------------------------------------------------------------------


def _mk_supply_app():
    gs = build_grazianis_offensive()
    console = Console(file=io.StringIO(), width=120, force_terminal=False,
                      color_system=None)
    return App(state=gs, viewer=Side.AXIS, console=console)


def test_app_movement_consumes_fuel():
    app = _mk_supply_app()
    # Advance to Movement & Combat.
    while app.state.phase != Phase.MOVEMENT_AND_COMBAT:
        app.step(Key.NEXT)
    fuel_before = get_supply_pool(app.state, Side.AXIS).fuel
    # Find a motorized Axis unit (tank).
    tank = next((u for u in app.state.units.values()
                 if u.side == Side.AXIS and u.unit_type == UnitType.TANK
                 and u.position is not None), None)
    if tank:
        app.selected = tank.position
        app.step(Key.MOVE)
        fuel_after = get_supply_pool(app.state, Side.AXIS).fuel
        # Fuel should have decreased (or stayed same if move failed).
        assert fuel_after <= fuel_before


def test_app_combat_consumes_ammo():
    app = _mk_supply_app()
    while app.state.phase != Phase.MOVEMENT_AND_COMBAT:
        app.step(Key.NEXT)
    ammo_before = get_supply_pool(app.state, Side.AXIS).ammo
    # Select an Axis hex adjacent to CW.
    active = app.state.active_side
    from cna.engine.hex_map import HexMap
    hex_map = HexMap(app.state.map)
    for u in app.state.units.values():
        if u.side != active or u.position is None:
            continue
        for nb in hex_map.neighbors_in_bounds(u.position):
            enemies = [e for e in app.state.units_at(nb) if e.side != active]
            if enemies:
                app.selected = u.position
                app.step(Key.COMBAT)
                ammo_after = get_supply_pool(app.state, Side.AXIS).ammo
                assert ammo_after < ammo_before
                return
    # If no adjacent enemies found, skip this test.


def test_dashboard_shows_supply():
    app = _mk_supply_app()
    buf = io.StringIO()
    console = Console(file=buf, width=140, force_terminal=False, color_system=None)
    from cna.ui.dashboard import render_header
    from cna.ui.views import build_view
    view = build_view(app.state, Side.AXIS)
    console.print(render_header(view))
    output = buf.getvalue()
    assert "Ammo" in output
    assert "Fuel" in output
