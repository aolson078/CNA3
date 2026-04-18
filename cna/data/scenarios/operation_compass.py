"""Section 60.0 — Scenario Group One: The Italians (Operation Compass).

Builds initial GameState for the two scenarios in this group:
  - Graziani's Offensive (Case 60.22): Game-Turn 1.I through 6.III.
  - The Italian Campaign (Case 60.23): Game-Turn 1.I through 20.III,
    which includes O'Connor's Operation Compass counteroffensive.

LAYER 1 SCOPE — ABBREVIATED DEPLOYMENT
The canonical Case 60.31 / 60.41 deployment places ~40 Axis and
~20 Commonwealth formations across ~60 named hexes, plus supply dumps,
air units, truck pools, and fleet counters we haven't modeled yet.
This module encodes a faithful but deliberately *condensed* subset
adequate for:
  - driving the PhaseDriver / initiative rules end-to-end,
  - giving the dashboard meaningful content,
  - demonstrating Case 60.6 (Italian turn-1 initiative predetermined).

Full-fidelity deployment is a separate task that requires:
  1. Hex map transcription (Case 4.0) — the Case 60.31 hex IDs like
     "C4218" must be translated to axial coords once the map is
     encoded in cna/data/maps/.
  2. Full OOB encoding (Case 60.31, 60.41) — via /encode-oob, which
     will need unit-stat ratings per the Organization-at-Arrival chart.
  3. Supply dump modeling (Case 60.34, 60.44) — requires Section 32
     (abstract) or Sections 45-58 (full logistics) to be encoded.

Items flagged TODO-60.X below reference the rulebook case they implement.
"""

from __future__ import annotations

from dataclasses import dataclass

from cna.engine.game_state import (
    GameState,
    HexCoord,
    MapHex,
    OperationsStage,
    OrgSize,
    Phase,
    Player,
    Side,
    TerrainType,
    Unit,
    UnitClass,
    UnitStats,
    UnitType,
    WeatherState,
)
from cna.rules.initiative import InitiativeRatings, set_initiative_ratings


# ---------------------------------------------------------------------------
# Scenario identifiers
# ---------------------------------------------------------------------------


SCENARIO_ID_GRAZIANI = "operation_compass.grazianis_offensive"
SCENARIO_ID_ITALIAN_CAMPAIGN = "operation_compass.italian_campaign"


# ---------------------------------------------------------------------------
# Named hexes (Case 60 deployment)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NamedHex:
    """A rulebook-named hex with a placeholder axial coordinate.

    The *rulebook_id* preserves the Case 60.3x designations (e.g. C4807 for
    Tobruk). The *coord* field is a provisional axial coord chosen to give
    a sensible spatial layout for the abbreviated map; it will be replaced
    when the full Case 4.0 hex map is transcribed.
    """

    name: str
    rulebook_id: str
    coord: HexCoord
    terrain: TerrainType
    port_capacity: int = 0
    has_airfield: bool = False
    has_landing_strip: bool = False
    controller: Side | None = None


# Provisional axial coords — roughly west-to-east along the coast.
# TODO-4.0: replace with real axial coords once the hex map is encoded.
_NAMED_HEXES: tuple[NamedHex, ...] = (
    # Axis-controlled (Libya) — west to east.
    NamedHex("Tripoli", "box", HexCoord(-14, 0), TerrainType.CITY,
            port_capacity=8, has_airfield=True, controller=Side.AXIS),
    NamedHex("El Agheila", "A1816", HexCoord(-10, 0), TerrainType.DESERT,
            has_landing_strip=True, controller=Side.AXIS),
    NamedHex("Benghazi", "B4827", HexCoord(-7, -1), TerrainType.CITY,
            port_capacity=4, controller=Side.AXIS),
    NamedHex("Barce", "B5504", HexCoord(-6, -1), TerrainType.TOWN,
            has_airfield=True, controller=Side.AXIS),
    NamedHex("Derna", "B5925", HexCoord(-4, -1), TerrainType.PORT,
            port_capacity=2, controller=Side.AXIS),
    NamedHex("Mechili", "B4921", HexCoord(-5, 1), TerrainType.DESERT,
            controller=Side.AXIS),
    NamedHex("Tobruk", "C4807", HexCoord(-2, -1), TerrainType.PORT,
            port_capacity=4, controller=Side.AXIS),
    NamedHex("El Adem", "C4507", HexCoord(-2, 0), TerrainType.DESERT,
            has_airfield=True, controller=Side.AXIS),
    NamedHex("Bardia", "C4321", HexCoord(-1, -1), TerrainType.TOWN,
            has_landing_strip=True, controller=Side.AXIS),
    NamedHex("Fort Capuzzo", "C4020", HexCoord(0, 0), TerrainType.DESERT,
            has_landing_strip=True, controller=Side.AXIS),
    NamedHex("Sidi Omar", "C3618", HexCoord(1, 1), TerrainType.DESERT,
            has_landing_strip=True, controller=Side.AXIS),
    NamedHex("Fort Maddalena", "C3019", HexCoord(2, 1), TerrainType.DESERT,
            controller=Side.AXIS),
    NamedHex("Giarabub", "C1014", HexCoord(4, 4), TerrainType.OASIS,
            has_landing_strip=True, controller=Side.AXIS),
    # Contested frontier (initially Axis per 60.31).
    NamedHex("Sidi Barrani", "C4131", HexCoord(3, -1), TerrainType.DESERT,
            has_landing_strip=True, controller=Side.COMMONWEALTH),
    NamedHex("Buq Buq", "C3926", HexCoord(4, -1), TerrainType.DESERT,
            has_landing_strip=True, controller=Side.COMMONWEALTH),
    # Commonwealth-controlled (Egypt).
    NamedHex("Mersa Matruh", "D3714", HexCoord(6, 0), TerrainType.PORT,
            port_capacity=2, has_airfield=True, controller=Side.COMMONWEALTH),
    NamedHex("Fuka", "D3323", HexCoord(7, -1), TerrainType.DESERT,
            has_landing_strip=True, controller=Side.COMMONWEALTH),
    NamedHex("El Alamein", "E1829", HexCoord(9, -1), TerrainType.DESERT,
            controller=Side.COMMONWEALTH),
    NamedHex("Alexandria", "E3614", HexCoord(11, -1), TerrainType.CITY,
            port_capacity=8, has_airfield=True, controller=Side.COMMONWEALTH),
    NamedHex("Cairo", "E1430", HexCoord(11, 1), TerrainType.CITY,
            has_airfield=True, controller=Side.COMMONWEALTH),
    NamedHex("Siwa", "C0127", HexCoord(6, 3), TerrainType.OASIS,
            has_landing_strip=True, controller=Side.COMMONWEALTH),
)


def _named_hex(name: str) -> NamedHex:
    for nh in _NAMED_HEXES:
        if nh.name == name:
            return nh
    raise KeyError(f"No named hex: {name}")


# ---------------------------------------------------------------------------
# Abbreviated OOB (Case 60.31 Axis, Case 60.41 Commonwealth)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _UnitSpec:
    """Compact unit spec used by the abbreviated OOB table.

    Case 60.31 / 60.41 — each entry represents a headline formation with
    placeholder ratings. Rating values are conservative Layer-1 defaults;
    full OA-chart fidelity is a separate task (see module docstring).
    """

    uid: str
    name: str
    unit_type: UnitType
    unit_class: UnitClass
    org_size: OrgSize
    max_toe: int
    cpa: int
    morale: int
    location: str  # Name of NamedHex or "off_map"


# Italian Initial Deployment — Case 60.31. Abbreviated to the headline
# divisions and a single representative armored formation. Item details
# like attached corps artillery and truck pools are deferred.
_AXIS_OOB: tuple[_UnitSpec, ...] = (
    _UnitSpec("ax.1ccnn", "1st CCNN Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=12, cpa=8, morale=0,
             location="Sidi Barrani"),
    _UnitSpec("ax.63cirene", "63rd Cirene Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=12, cpa=8, morale=0,
             location="Fort Capuzzo"),
    _UnitSpec("ax.1libyan", "1st Libyan Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=10, cpa=8, morale=-1,
             location="Fort Capuzzo"),
    _UnitSpec("ax.2libyan", "2nd Libyan Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=10, cpa=8, morale=-1,
             location="Sidi Omar"),
    _UnitSpec("ax.62marmar", "62nd Marmarica Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=12, cpa=8, morale=0,
             location="Sidi Omar"),
    _UnitSpec("ax.maletti", "Maletti Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=10, cpa=8, morale=0,
             location="Sidi Omar"),
    _UnitSpec("ax.64catanz", "64th Catanzaro Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=12, cpa=8, morale=0,
             location="Bardia"),
    _UnitSpec("ax.4ccnn", "4th CCNN Division", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.DIVISION, max_toe=12, cpa=8, morale=0,
             location="Bardia"),
    _UnitSpec("ax.trivoli", "Trivoli Regiment", UnitType.TANK,
             UnitClass.ARMOR, OrgSize.BRIGADE, max_toe=6, cpa=10, morale=1,
             location="Bardia"),
    _UnitSpec("ax.libtkcmd", "Libyan Tank Command", UnitType.HEADQUARTERS,
             UnitClass.ARMOR, OrgSize.DIVISION, max_toe=6, cpa=10, morale=1,
             location="Tobruk"),
    _UnitSpec("ax.aresca", "Aresca Regiment", UnitType.TANK,
             UnitClass.ARMOR, OrgSize.BRIGADE, max_toe=6, cpa=10, morale=0,
             location="Sidi Omar"),
    _UnitSpec("ax.bengaz", "Benghazi Garrison", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.BATTALION, max_toe=4, cpa=0, morale=-1,
             location="Benghazi"),
    _UnitSpec("ax.derna", "Derna Garrison", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.BATTALION, max_toe=4, cpa=0, morale=-1,
             location="Derna"),
    _UnitSpec("ax.giarabub", "Giarabub Garrison", UnitType.INFANTRY,
             UnitClass.INFANTRY, OrgSize.BATTALION, max_toe=4, cpa=0, morale=-1,
             location="Giarabub"),
    # TODO-60.31: 30+ additional formations (Saharan Det, XVIII/XXXII Lib,
    # garrison units, Tripolitania forces, coastal shipping, airfields).
)


# Commonwealth Initial Deployment — Case 60.41.
_COMMONWEALTH_OOB: tuple[_UnitSpec, ...] = (
    _UnitSpec("cw.7armd", "7th Armoured Division",
             UnitType.HEADQUARTERS, UnitClass.ARMOR, OrgSize.DIVISION,
             max_toe=14, cpa=12, morale=2, location="Mersa Matruh"),
    _UnitSpec("cw.4ind", "4th Indian Division",
             UnitType.HEADQUARTERS, UnitClass.INFANTRY, OrgSize.DIVISION,
             max_toe=14, cpa=10, morale=2, location="Mersa Matruh"),
    _UnitSpec("cw.matruh", "Matruh Garrison",
             UnitType.INFANTRY, UnitClass.INFANTRY, OrgSize.BRIGADE,
             max_toe=8, cpa=8, morale=1, location="Mersa Matruh"),
    _UnitSpec("cw.2nz", "2nd New Zealand Division",
             UnitType.HEADQUARTERS, UnitClass.INFANTRY, OrgSize.DIVISION,
             max_toe=12, cpa=10, morale=2, location="Alexandria"),
    _UnitSpec("cw.16bde", "16th Infantry Brigade",
             UnitType.INFANTRY, UnitClass.INFANTRY, OrgSize.BRIGADE,
             max_toe=8, cpa=10, morale=2, location="El Alamein"),
    _UnitSpec("cw.2scots", "2nd Scots Guards",
             UnitType.INFANTRY, UnitClass.INFANTRY, OrgSize.BATTALION,
             max_toe=6, cpa=10, morale=2, location="Sidi Barrani"),
    _UnitSpec("cw.3cold", "3rd Coldstream Guards",
             UnitType.INFANTRY, UnitClass.INFANTRY, OrgSize.BATTALION,
             max_toe=6, cpa=10, morale=2, location="Buq Buq"),
    _UnitSpec("cw.11hus", "11th Hussars",
             UnitType.RECCE, UnitClass.ARMOR, OrgSize.BATTALION,
             max_toe=4, cpa=14, morale=3, location="Sidi Barrani"),
    _UnitSpec("cw.6aus", "6th Australian Division (Training)",
             UnitType.HEADQUARTERS, UnitClass.INFANTRY, OrgSize.DIVISION,
             max_toe=12, cpa=10, morale=1, location="Cairo"),
    # TODO-60.41: remaining corps artillery, regional artillery regiments,
    # Malta forces, Free French detachments, fleet counters (Case 60.45).
)


def _unit_from_spec(spec: _UnitSpec, side: Side, hex_index: dict[str, HexCoord]) -> Unit:
    pos = hex_index.get(spec.location) if spec.location != "off_map" else None
    return Unit(
        id=spec.uid,
        side=side,
        name=spec.name,
        unit_type=spec.unit_type,
        unit_class=spec.unit_class,
        org_size=spec.org_size,
        stats=UnitStats(
            capability_point_allowance=spec.cpa,
            max_toe_strength=spec.max_toe,
            basic_morale=spec.morale,
        ),
        position=pos,
        current_toe=spec.max_toe,
        current_morale=spec.morale,
    )


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def _build_common(scenario_id: str, name: str, length_turns: int) -> GameState:
    """Shared state construction for both sub-scenarios in Group One.

    Case 60.3, 60.4, 60.5, 60.6 — Axis and Commonwealth deployment, air
    facilities, and initiative configuration.
    """
    state = GameState()
    state.scenario_id = scenario_id
    state.game_turn = 1
    state.operations_stage = OperationsStage.FIRST
    state.phase = Phase.INITIATIVE_DETERMINATION
    state.active_side = Side.AXIS  # Axis acts first by Case 60.6.
    state.weather = WeatherState.CLEAR  # TODO-29.0: roll weather normally from turn 1.

    state.players[Side.AXIS] = Player(side=Side.AXIS, name="Italian Player")
    state.players[Side.COMMONWEALTH] = Player(
        side=Side.COMMONWEALTH, name="Commonwealth Player"
    )

    # Build the abbreviated map.
    hex_index: dict[str, HexCoord] = {}
    for nh in _NAMED_HEXES:
        mh = MapHex(
            coord=nh.coord,
            terrain=nh.terrain,
            name=nh.name,
            port_capacity=nh.port_capacity,
            has_airfield=nh.has_airfield,
            has_landing_strip=nh.has_landing_strip,
            controller=nh.controller,
        )
        state.map[nh.coord] = mh
        hex_index[nh.name] = nh.coord

    # Populate OOB.
    for spec in _AXIS_OOB:
        u = _unit_from_spec(spec, Side.AXIS, hex_index)
        state.units[u.id] = u
    for spec in _COMMONWEALTH_OOB:
        u = _unit_from_spec(spec, Side.COMMONWEALTH, hex_index)
        state.units[u.id] = u

    # Case 60.6 — Italian Player has Initiative for the entire first Game-Turn.
    # The initiative handler reads this key on turn 1 to bypass the roll.
    state.extras["scenario_turn1_initiative"] = Side.AXIS.value

    # Case 7.14 example values (Axis no-Germans = 1, CW turns 1-42 = 3).
    # Turn 1 of the Italian Campaign is 15 September 1940.
    set_initiative_ratings(state, InitiativeRatings(axis=1, commonwealth=3))

    # Scenario metadata for the UI / victory checker.
    state.extras["scenario_name"] = name
    state.extras["scenario_length_turns"] = length_turns
    state.extras["scenario_start_date"] = "1940-09-15"

    state.log(
        f"Scenario loaded: {name}",
        side=None,
        category="scenario",
        data={"scenario_id": scenario_id, "length_turns": length_turns},
    )
    return state


def build_grazianis_offensive() -> GameState:
    """Case 60.22 — Graziani's Offensive (6 Game-Turns).

    Italian offensive into Egypt, ending before O'Connor's counterstroke.
    """
    return _build_common(
        scenario_id=SCENARIO_ID_GRAZIANI,
        name="Graziani's Offensive",
        length_turns=6,
    )


def build_italian_campaign() -> GameState:
    """Case 60.23 — The Italian Campaign (20 Game-Turns).

    Extends Graziani's Offensive through O'Connor's Operation Compass
    counteroffensive; ends end of Game-Turn 20.III.
    """
    return _build_common(
        scenario_id=SCENARIO_ID_ITALIAN_CAMPAIGN,
        name="The Italian Campaign",
        length_turns=20,
    )
