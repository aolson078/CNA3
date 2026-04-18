"""Tests for Sections 16-32 rules modules.

Covers: Patrols (16), Morale (17), Reserves (18), Organization (19),
Reinforcements (20), Breakdown (21), Repair (22), Engineers (23),
Construction (24), Fortifications (25), Minefields (26), Desert
Raiders (27), Prisoners (28), Weather (29), Naval (30), Rommel (31),
Abstract Supply (32).
"""

from __future__ import annotations

import pytest

from cna.engine.dice import DiceRoller
from cna.engine.errors import RuleViolationError
from cna.engine.game_state import (
    CohesionLevel,
    GameState,
    HexCoord,
    MapHex,
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
from cna.rules.capability_points import apply_disorganization


def _u(uid: str = "u1", side: Side = Side.AXIS, cpa: int = 20,
       ut: UnitType = UnitType.INFANTRY, org: OrgSize = OrgSize.BATTALION,
       toe: int = 6, morale: int = 1, at: HexCoord = HexCoord(0, 0),
       **kw) -> Unit:
    return Unit(
        id=uid, side=side, name=uid, unit_type=ut, unit_class=UnitClass.INFANTRY,
        org_size=org, stats=UnitStats(capability_point_allowance=cpa,
                                      max_toe_strength=toe, basic_morale=morale),
        position=at, current_toe=toe, current_morale=morale, **kw,
    )


def _gs(**kw) -> GameState:
    gs = GameState()
    gs.map = {HexCoord(0, 0): MapHex(coord=HexCoord(0, 0), terrain=TerrainType.DESERT)}
    gs.players = {
        Side.AXIS: Player(side=Side.AXIS),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH),
    }
    return gs


# ---------------------------------------------------------------------------
# §16 Patrols
# ---------------------------------------------------------------------------

def test_patrol_recce_eligible():
    from cna.rules.combat.patrols import can_patrol
    u = _u(ut=UnitType.RECCE)
    assert can_patrol(u)

def test_patrol_infantry_not_eligible():
    from cna.rules.combat.patrols import can_patrol
    u = _u(ut=UnitType.INFANTRY)
    assert not can_patrol(u)

def test_patrol_resolve():
    from cna.rules.combat.patrols import resolve_patrol, PatrolSurvival
    u = _u(ut=UnitType.RECCE, toe=3)
    targets = [_u("e1", side=Side.COMMONWEALTH)]
    result = resolve_patrol(u, HexCoord(1, 0), targets, DiceRoller(seed=42))
    assert result.survival in PatrolSurvival


# ---------------------------------------------------------------------------
# §17 Morale
# ---------------------------------------------------------------------------

def test_effective_morale_basic():
    from cna.rules.morale import effective_morale
    u = _u(morale=2)
    assert effective_morale(u) == 2

def test_effective_morale_with_cohesion():
    from cna.rules.morale import effective_morale
    u = _u(morale=2)
    apply_disorganization(u, 6)
    assert effective_morale(u) < 2

def test_morale_differential():
    from cna.rules.morale import morale_differential
    att = [_u("a", morale=2)]
    defn = [_u("d", morale=-1)]
    diff = morale_differential(att, defn)
    assert diff > 0

def test_can_train():
    from cna.rules.morale import can_train
    u = _u(morale=0)
    u.stats = UnitStats(basic_morale=2, max_toe_strength=6)
    assert can_train(u)

def test_training_completion():
    from cna.rules.morale import apply_training_completion
    u = _u(morale=0)
    u.stats = UnitStats(basic_morale=2, max_toe_strength=6)
    apply_training_completion(u)
    assert u.current_morale == 1

def test_voluntary_surrender():
    from cna.rules.morale import can_voluntarily_surrender
    u = _u(morale=-3)
    assert can_voluntarily_surrender(u)

def test_morale_after_combat():
    from cna.rules.morale import check_morale_after_combat
    u = _u(morale=1)
    result = check_morale_after_combat(u, won_assault=True, dice=DiceRoller(seed=1))
    assert result.old_morale == 1


# ---------------------------------------------------------------------------
# §18 Reserves
# ---------------------------------------------------------------------------

def test_reserve_eligible():
    from cna.rules.reserves import can_designate_reserve
    u = _u(ut=UnitType.TANK, cpa=25)
    assert can_designate_reserve(u)

def test_reserve_infantry_not_eligible():
    from cna.rules.reserves import can_designate_reserve
    u = _u(ut=UnitType.INFANTRY, cpa=8)
    assert not can_designate_reserve(u)

def test_designate_reserve():
    from cna.rules.reserves import designate_reserve
    u = _u(ut=UnitType.TANK, cpa=25)
    designate_reserve(u)
    assert u.reserve_status == ReserveStatus.RESERVE_I

def test_release_reserve():
    from cna.rules.reserves import release_reserve
    u = _u(ut=UnitType.TANK)
    u.reserve_status = ReserveStatus.RESERVE_I
    release_reserve(u)
    assert u.reserve_status == ReserveStatus.NONE

def test_release_all_reserves():
    from cna.rules.reserves import release_all_reserves
    gs = _gs()
    u = _u("t1", ut=UnitType.TANK, cpa=25)
    u.reserve_status = ReserveStatus.RESERVE_I
    gs.units[u.id] = u
    released = release_all_reserves(gs, Side.AXIS)
    assert u.id in released
    assert u.reserve_status == ReserveStatus.NONE


# ---------------------------------------------------------------------------
# §19 Organization
# ---------------------------------------------------------------------------

def test_attach_unit():
    from cna.rules.organization import attach_unit
    gs = _gs()
    parent = _u("hq", ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION, cpa=20)
    child = _u("bn1", cpa=20)
    gs.units[parent.id] = parent
    gs.units[child.id] = child
    attach_unit(gs, parent.id, child.id)
    assert child.id in parent.attached_unit_ids
    assert child.parent_id == parent.id

def test_detach_unit():
    from cna.rules.organization import attach_unit, detach_unit
    gs = _gs()
    parent = _u("hq", ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION, cpa=20)
    child = _u("bn1", cpa=20)
    gs.units[parent.id] = parent
    gs.units[child.id] = child
    attach_unit(gs, parent.id, child.id)
    detach_unit(gs, parent.id, child.id)
    assert child.id not in parent.attached_unit_ids

def test_absorb_replacements():
    from cna.rules.organization import absorb_replacements
    u = _u(toe=4)
    u.stats = UnitStats(max_toe_strength=6, capability_point_allowance=20)
    absorb_replacements(u, 2)
    assert u.current_toe == 6


# ---------------------------------------------------------------------------
# §20 Reinforcements
# ---------------------------------------------------------------------------

def test_can_withdraw():
    from cna.rules.units.reinforcements import can_withdraw
    u = _u(toe=5)
    u.stats = UnitStats(max_toe_strength=6)
    assert can_withdraw(u)  # 5/6 = 83% > 75%

def test_cannot_withdraw_below_threshold():
    from cna.rules.units.reinforcements import can_withdraw
    u = _u(toe=3)
    u.stats = UnitStats(max_toe_strength=6)
    assert not can_withdraw(u)  # 3/6 = 50% < 75%


# ---------------------------------------------------------------------------
# §21 Breakdown
# ---------------------------------------------------------------------------

def test_breakdown_eligible():
    from cna.rules.units.breakdown import is_breakdown_eligible
    assert is_breakdown_eligible(_u(ut=UnitType.TANK))
    assert is_breakdown_eligible(_u(ut=UnitType.TRUCK))
    assert not is_breakdown_eligible(_u(ut=UnitType.INFANTRY))

def test_breakdown_below_threshold():
    from cna.rules.units.breakdown import check_breakdown, BREAKDOWN_CHECK_THRESHOLD
    u = _u(ut=UnitType.TANK)
    result = check_breakdown(u, BREAKDOWN_CHECK_THRESHOLD, DiceRoller(seed=1))
    assert result.toe_lost == 0

def test_breakdown_above_threshold():
    from cna.rules.units.breakdown import check_breakdown
    u = _u(ut=UnitType.TANK, toe=10)
    result = check_breakdown(u, 20, DiceRoller(seed=42))
    assert isinstance(result.loss_pct, int)


# ---------------------------------------------------------------------------
# §22 Repair
# ---------------------------------------------------------------------------

def test_field_repair():
    from cna.rules.units.repair import attempt_field_repair
    u = _u(ut=UnitType.TRUCK, toe=3)
    u.broken_down = True
    result = attempt_field_repair(u, DiceRoller(seed=1))
    assert isinstance(result.dice_roll, int)


# ---------------------------------------------------------------------------
# §23 Engineers
# ---------------------------------------------------------------------------

def test_is_engineer():
    from cna.rules.terrain.engineers import is_engineer
    assert is_engineer(_u(ut=UnitType.ENGINEER))
    assert not is_engineer(_u(ut=UnitType.INFANTRY))


# ---------------------------------------------------------------------------
# §24 Construction
# ---------------------------------------------------------------------------

def test_construction_costs():
    from cna.rules.terrain.construction import ConstructionType, CONSTRUCTION_COSTS
    cost = CONSTRUCTION_COSTS[ConstructionType.MINEFIELD]
    assert cost.ops_stages == 1
    assert cost.stores == 15
    assert cost.ammo == 15


# ---------------------------------------------------------------------------
# §25 Fortifications
# ---------------------------------------------------------------------------

def test_fortification_shifts():
    from cna.rules.terrain.fortifications import (
        FortificationLevel, FORT_CLOSE_ASSAULT_SHIFTS, ignores_pinned,
    )
    assert FORT_CLOSE_ASSAULT_SHIFTS[FortificationLevel.LEVEL_2] == -2
    assert ignores_pinned(FortificationLevel.LEVEL_3)
    assert not ignores_pinned(FortificationLevel.LEVEL_2)


# ---------------------------------------------------------------------------
# §26 Minefields
# ---------------------------------------------------------------------------

def test_minefield_vehicle_loss():
    from cna.rules.terrain.minefields import vehicle_minefield_loss_check
    losses = vehicle_minefield_loss_check(3, DiceRoller(seed=42))
    assert isinstance(losses, int) and losses >= 0


# ---------------------------------------------------------------------------
# §27 Desert Raiders
# ---------------------------------------------------------------------------

def test_spot_raider():
    from cna.rules.special.desert_raiders import attempt_spot
    result = attempt_spot(DiceRoller(seed=42))
    assert isinstance(result, bool)

def test_raid_resolve():
    from cna.rules.special.desert_raiders import resolve_raid, RaidType
    result = resolve_raid(RaidType.PIPELINE, DiceRoller(seed=1))
    assert isinstance(result.success, bool)


# ---------------------------------------------------------------------------
# §28 Prisoners
# ---------------------------------------------------------------------------

def test_prisoner_group():
    from cna.rules.special.prisoners import PrisonerGroup
    pg = PrisonerGroup(side_captured="axis", prisoner_points=10, guard_points=10)
    assert pg.is_guarded
    assert pg.stores_required == 2  # 10/5 = 2


# ---------------------------------------------------------------------------
# §29 Weather
# ---------------------------------------------------------------------------

def test_determine_weather():
    from cna.rules.special.weather import determine_weather
    result = determine_weather(1, DiceRoller(seed=42))
    assert result.weather in WeatherState
    assert result.season.value in ("autumn", "winter", "spring", "summer")

def test_weather_handler():
    from cna.rules.special.weather import handle_weather_phase
    gs = _gs()
    gs.phase = Phase.WEATHER_DETERMINATION
    handle_weather_phase(gs, None)
    assert gs.weather in WeatherState


# ---------------------------------------------------------------------------
# §30 Naval
# ---------------------------------------------------------------------------

def test_naval_unit():
    from cna.rules.special.naval import NavalUnit, ShipType
    ship = NavalUnit(id="bb1", ship_type=ShipType.BATTLESHIP, gun_rating=8, aa_rating=4)
    assert not ship.is_at_sea
    assert ship.can_sortie is False  # needs 2 ops in port first
    ship.ops_in_port = 2
    assert ship.can_sortie


# ---------------------------------------------------------------------------
# §31 Rommel
# ---------------------------------------------------------------------------

def test_rommel_recall():
    from cna.rules.special.rommel import check_rommel_recall
    result = check_rommel_recall(DiceRoller(seed=42))
    assert isinstance(result, bool)

def test_rommel_status():
    from cna.rules.special.rommel import RommelStatus
    r = RommelStatus(on_map=True)
    assert r.on_map


# ---------------------------------------------------------------------------
# §32 Abstract Supply
# ---------------------------------------------------------------------------

def test_supply_unit():
    from cna.rules.abstract.supply import SupplyUnit
    su = SupplyUnit(id="s1", side=Side.AXIS, position=HexCoord(0, 0),
                    ammo=40, fuel=60)
    assert not su.is_empty

def test_supply_line_range():
    from cna.rules.abstract.supply import supply_line_range
    u = _u(cpa=20)
    assert supply_line_range(u) == 10

def test_is_in_supply():
    from cna.rules.abstract.supply import is_in_supply
    gs = _gs()
    u = _u(cpa=20)
    gs.units[u.id] = u
    assert is_in_supply(gs, u, [HexCoord(0, 0)])
    assert not is_in_supply(gs, u, [HexCoord(99, 99)])

def test_motorization_loss():
    from cna.rules.abstract.supply import MotorizationPool
    pool = MotorizationPool(side=Side.AXIS, points=100)
    loss = pool.apply_monthly_loss()
    assert loss == 5
    assert pool.points == 95
