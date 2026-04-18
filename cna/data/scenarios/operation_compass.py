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

from cna.data.maps.map_builder import build_operational_map
from cna.data.oob.commonwealth import build_commonwealth_oob
from cna.data.oob.italian import build_italian_oob
from cna.engine.game_state import (
    GameState,
    OperationsStage,
    Phase,
    Player,
    Side,
    WeatherState,
)
from cna.rules.abstract.supply import init_supply_pools
from cna.rules.initiative import InitiativeRatings, set_initiative_ratings


# ---------------------------------------------------------------------------
# Scenario identifiers
# ---------------------------------------------------------------------------


SCENARIO_ID_GRAZIANI = "operation_compass.grazianis_offensive"
SCENARIO_ID_ITALIAN_CAMPAIGN = "operation_compass.italian_campaign"


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

    # Build the full operational map from the hex catalog.
    state.map = build_operational_map()

    # Populate OOB from real combat-rated unit data.
    for u in build_italian_oob():
        state.units[u.id] = u
    for u in build_commonwealth_oob():
        state.units[u.id] = u

    # Case 60.6 — Italian Player has Initiative for the entire first Game-Turn.
    # The initiative handler reads this key on turn 1 to bypass the roll.
    state.extras["scenario_turn1_initiative"] = Side.AXIS.value

    # Case 7.14 example values (Axis no-Germans = 1, CW turns 1-42 = 3).
    # Turn 1 of the Italian Campaign is 15 September 1940.
    set_initiative_ratings(state, InitiativeRatings(axis=1, commonwealth=3))

    # Case 60.92 — Abstract supply (Land Game Only).
    # Axis: dumps at Tobruk, Bardia, Benghazi, Derna, Tripoli + field dumps.
    # CW: dumps at Matruh, Sidi Barrani + unlimited at Cairo/Alexandria.
    # Simplified to aggregate pools.
    init_supply_pools(
        state,
        axis_ammo=3000, axis_fuel=2500,
        cw_ammo=5000, cw_fuel=7000,
    )

    # Case 60.47 / 20.11 — Reinforcement schedule.
    # Historical arrivals for Operation Compass / Italian Campaign.
    state.extras["reinforcement_schedule"] = [
        {"unit_id": "cw.7rtr", "arrival_turn": 7, "hex": "Alexandria",
         "side": "commonwealth"},
        {"unit_id": "cw.2rtr", "arrival_turn": 8, "hex": "Alexandria",
         "side": "commonwealth"},
        {"unit_id": "cw.19aus_bde", "arrival_turn": 10, "hex": "Cairo",
         "side": "commonwealth"},
        {"unit_id": "cw.6div_arty", "arrival_turn": 10, "hex": "Cairo",
         "side": "commonwealth"},
    ]
    state.extras["reinforcement_units"] = {
        "cw.7rtr": {
            "name": "7th RTR", "unit_type": "tank", "unit_class": "armor",
            "org_size": "battalion", "cpa": 25, "toe": 4, "morale": 2,
            "off_ca": 7, "def_ca": 7, "anti_armor": 5, "armor_prot": 6,
        },
        "cw.2rtr": {
            "name": "2nd RTR", "unit_type": "tank", "unit_class": "armor",
            "org_size": "battalion", "cpa": 25, "toe": 4, "morale": 2,
            "off_ca": 7, "def_ca": 7, "anti_armor": 5, "armor_prot": 2,
        },
        "cw.19aus_bde": {
            "name": "19th Australian Brigade", "unit_type": "infantry",
            "unit_class": "infantry", "org_size": "brigade",
            "cpa": 8, "toe": 8, "morale": 2, "off_ca": 7, "def_ca": 7,
        },
        "cw.6div_arty": {
            "name": "6th Div Artillery", "unit_type": "artillery",
            "unit_class": "gun", "org_size": "battalion",
            "cpa": 15, "toe": 4, "morale": 2, "barrage": 12,
            "off_ca": 2, "def_ca": 3, "anti_armor": 3,
        },
    }

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
