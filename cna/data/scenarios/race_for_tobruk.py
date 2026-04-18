"""Section 61.0 — Scenario Group Two: Race for Tobruk.

Implements Cases 61.1-61.8: Rommel's arrival and the Axis counteroffensive
in Cyrenaica, February-June 1941.

Case 61.2 — Starts Game-Turn 26 OpStage 3, ends Game-Turn 38.
Estimated play time: 75-125 hours (board game).

Sources:
  - Case 61.31: Commonwealth deployment.
  - Case 61.41: Axis deployment (German + Italian).
  - Case 61.5: Initiative — Axis has Initiative for first Game-Turn.
"""

from __future__ import annotations

from cna.data.maps.map_builder import build_operational_map
from cna.data.maps.coords import hex_id_to_coord
from cna.engine.game_state import (
    GameState,
    OrgSize,
    OperationsStage,
    Phase,
    Player,
    Side,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
    WeatherState,
)
from cna.rules.abstract.supply import init_supply_pools
from cna.rules.initiative import InitiativeRatings, set_initiative_ratings


SCENARIO_ID = "race_for_tobruk"


def _u(uid: str, side: Side, name: str, hex_id: str, *,
       ut: UnitType = UnitType.INFANTRY, uc: UnitClass = UnitClass.INFANTRY,
       org: OrgSize = OrgSize.BATTALION, cpa: int = 8, toe: int = 6,
       morale: int = 1, barrage: int = 0, anti_armor: int = 0,
       armor_prot: int = 0, off_ca: int = 7, def_ca: int = 7,
       aa: int = 0, fuel_rate: int = 0, breakdown_adj: int = 0) -> Unit:
    return Unit(
        id=uid, side=side, name=name,
        unit_type=ut, unit_class=uc, org_size=org,
        stats=UnitStats(
            capability_point_allowance=cpa, max_toe_strength=toe,
            basic_morale=morale, barrage_rating=barrage,
            anti_armor_strength=anti_armor, armor_protection_rating=armor_prot,
            offensive_close_assault=off_ca, defensive_close_assault=def_ca,
            anti_aircraft_rating=aa, fuel_rate=fuel_rate,
            breakdown_adjustment=breakdown_adj,
        ),
        position=hex_id_to_coord(hex_id), current_toe=toe, current_morale=morale,
    )


AX = Side.AXIS
CW = Side.COMMONWEALTH


def _build_axis_units() -> list[Unit]:
    """Case 61.41 — Axis forces for Race for Tobruk."""
    return [
        # German units near El Agheila (A1816).
        _u("ax.5lregt", AX, "5th Light Div Recce", "A1816",
           ut=UnitType.RECCE, uc=UnitClass.ARMOR, cpa=45,
           toe=3, morale=2, anti_armor=3, armor_prot=1, off_ca=4, def_ca=3),
        _u("ax.5mg", AX, "5th Light MG Bn", "A1816",
           cpa=20, toe=6, morale=2, off_ca=8, def_ca=9),
        _u("ax.5pz_abt", AX, "5th Panzer Abteilung", "A1816",
           ut=UnitType.TANK, uc=UnitClass.ARMOR, org=OrgSize.BATTALION,
           cpa=25, toe=4, morale=2, anti_armor=7, armor_prot=3,
           off_ca=7, def_ca=5, fuel_rate=2, breakdown_adj=0),
        _u("ax.5arty", AX, "5th Light Artillery", "A1816",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN,
           cpa=15, toe=3, morale=2, barrage=14, off_ca=2, def_ca=3),
        _u("ax.5at", AX, "5th Light Anti-Tank", "A1816",
           ut=UnitType.ANTI_TANK, uc=UnitClass.GUN,
           cpa=15, toe=3, morale=2, anti_armor=8, off_ca=1, def_ca=2),

        # Ariete Division (within 2 hexes of El Agheila).
        _u("ax.ariete_hq", AX, "Ariete Division HQ", "A1816",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=10, toe=2, morale=1, off_ca=2, def_ca=2),
        _u("ax.ariete_tank", AX, "Ariete Tank Regt", "A1816",
           ut=UnitType.TANK, uc=UnitClass.ARMOR, org=OrgSize.BRIGADE,
           cpa=25, toe=6, morale=1, anti_armor=4, armor_prot=3,
           off_ca=5, def_ca=4, fuel_rate=2, breakdown_adj=1),

        # Italian divisions between Ras el Ali and Nofilia.
        _u("ax.pavia", AX, "Pavia Division", "A2021",
           org=OrgSize.DIVISION, toe=10, morale=0, off_ca=6, def_ca=6),
        _u("ax.bologna", AX, "Bologna Division", "A2021",
           org=OrgSize.DIVISION, toe=10, morale=0, off_ca=6, def_ca=6),
        _u("ax.brescia", AX, "Brescia Division", "A2109",
           org=OrgSize.DIVISION, toe=10, morale=0, off_ca=6, def_ca=6),
        _u("ax.savona", AX, "Savona Division", "A2109",
           org=OrgSize.DIVISION, toe=10, morale=0, off_ca=6, def_ca=6),

        # Trento Division in Tripoli.
        _u("ax.trento", AX, "Trento Division", "A2802",
           org=OrgSize.DIVISION, toe=10, morale=0, off_ca=6, def_ca=6),
    ]


def _build_cw_units() -> list[Unit]:
    """Case 61.31 — Commonwealth forces for Race for Tobruk."""
    return [
        # 3rd Armoured Brigade at A2022.
        _u("cw.3armbde", CW, "3rd Armoured Bde", "A2629",
           ut=UnitType.TANK, uc=UnitClass.ARMOR, org=OrgSize.BRIGADE,
           cpa=25, toe=6, morale=2, anti_armor=5, armor_prot=2,
           off_ca=6, def_ca=5, fuel_rate=2, breakdown_adj=1),

        # 2nd Support Group.
        _u("cw.2sptgrp", CW, "2nd Support Group", "A2629",
           org=OrgSize.BRIGADE, cpa=20, toe=8, morale=2,
           off_ca=7, def_ca=7),

        # 2nd Armoured Division HQ.
        _u("cw.2armd_hq", CW, "2nd Armoured Div HQ", "A2629",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=10, toe=2, morale=2, off_ca=2, def_ca=2),

        # 3rd Indian Motor Brigade at El Adem.
        _u("cw.3indmot", CW, "3rd Indian Motor Bde", "C4507",
           org=OrgSize.BRIGADE, cpa=20, toe=6, morale=2,
           off_ca=7, def_ca=7, is_motorized=True),

        # 9th Australian Division at Tobruk.
        _u("cw.9aus_hq", CW, "9th Australian Div HQ", "C4807",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=10, toe=2, morale=2, off_ca=2, def_ca=2),
        _u("cw.26aus", CW, "26th Australian Bde", "C4807",
           org=OrgSize.BRIGADE, toe=8, morale=2, off_ca=8, def_ca=8),
        _u("cw.24aus", CW, "24th Australian Bde", "B4827",
           org=OrgSize.BRIGADE, toe=8, morale=2, off_ca=8, def_ca=8),
        _u("cw.20aus", CW, "20th Australian Bde", "B4827",
           org=OrgSize.BRIGADE, toe=8, morale=2, off_ca=8, def_ca=8),

        # Tobruk garrison artillery.
        _u("cw.1rha_rt", CW, "1st RHA", "C4807",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN,
           cpa=15, toe=4, morale=2, barrage=12, anti_armor=3,
           off_ca=2, def_ca=3),
        _u("cw.51field_rt", CW, "51st Field Arty Regt", "B4827",
           ut=UnitType.ARTILLERY, uc=UnitClass.GUN,
           cpa=15, toe=4, morale=2, barrage=12, anti_armor=3,
           off_ca=2, def_ca=3),
        _u("cw.65at_rt", CW, "65th Anti-Tank Regt", "C4807",
           ut=UnitType.ANTI_TANK, uc=UnitClass.GUN,
           cpa=15, toe=4, morale=2, anti_armor=6, off_ca=1, def_ca=2),

        # Alexandria area.
        _u("cw.7armd_hq_rt", CW, "7th Armoured Div HQ", "E3613",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=10, toe=2, morale=2, off_ca=2, def_ca=2),
        _u("cw.22gds", CW, "22nd Guards Bde", "E3613",
           org=OrgSize.BRIGADE, toe=8, morale=2, off_ca=8, def_ca=9),
        _u("cw.70div_hq", CW, "70th Infantry Div HQ", "E3613",
           ut=UnitType.HEADQUARTERS, org=OrgSize.DIVISION,
           cpa=10, toe=2, morale=1, off_ca=2, def_ca=2),
    ]


def build_race_for_tobruk() -> GameState:
    """Case 61.2 — Race for Tobruk (Game-Turns 26-38).

    Rommel's arrival and the Axis counteroffensive into Cyrenaica.
    """
    state = GameState()
    state.scenario_id = SCENARIO_ID
    state.game_turn = 26
    state.operations_stage = OperationsStage.THIRD
    state.phase = Phase.INITIATIVE_DETERMINATION
    state.active_side = Side.AXIS
    state.weather = WeatherState.CLEAR

    state.players = {
        Side.AXIS: Player(side=Side.AXIS, name="Axis (Germany + Italy)"),
        Side.COMMONWEALTH: Player(side=Side.COMMONWEALTH, name="Commonwealth"),
    }

    state.map = build_operational_map()

    for u in _build_axis_units():
        state.units[u.id] = u
    for u in _build_cw_units():
        state.units[u.id] = u

    # Case 61.5: Axis has Initiative for first Game-Turn.
    state.extras["scenario_turn1_initiative"] = Side.AXIS.value
    # Rommel present → Axis rating 3 (Case 7.2).
    set_initiative_ratings(state, InitiativeRatings(axis=3, commonwealth=3))

    # Abstract supply (Case 61.36/61.44).
    init_supply_pools(state, axis_ammo=2000, axis_fuel=1500,
                      cw_ammo=4200, cw_fuel=3050)

    state.extras["scenario_name"] = "Race for Tobruk"
    state.extras["scenario_length_turns"] = 38
    state.extras["scenario_start_date"] = "1941-02-15"

    state.log("Scenario loaded: Race for Tobruk", side=None, category="scenario")
    return state
