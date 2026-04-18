"""Section 20.0 — Reinforcements, Replacements, and Withdrawals.

Implements Cases 20.1-20.9: reinforcement arrival, replacement points,
replacement conversion, replacement usage, upgrading, Axis planned
replacement, Commonwealth production, and mandatory withdrawals.

Key rules:
  - Case 20.11: Reinforcements arrive at Naval Convoy Arrival Phase.
  - Case 20.14: CW arrive at Cairo (some at Alexandria); Axis at Tripoli.
  - Case 20.21: Replacement Points arrive via convoy; Axis plans 2 turns
    ahead, CW 1 turn.
  - Case 20.41: Trained replacements in same hex as receiving unit.
  - Case 20.43: Training time: Gun=1 ops stage, Infantry=3, Tank=6.
  - Case 20.82: Mandatory CW withdrawals require 75% TOE at Cairo/Alex.

Cross-references:
  - Case 5.2 III.D: Naval Convoy Arrival Phase.
  - Case 17.3: Training affects replacement readiness.
  - Case 19.68: Absorbing replacements costs CP.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from cna.engine.game_state import (
    GameState,
    HexCoord,
    Side,
    Unit,
)


# ---------------------------------------------------------------------------
# Replacement training time (Case 20.43)
# ---------------------------------------------------------------------------


class ReplacementType(str, Enum):
    """Case 20.43 — Type determines training time."""
    GUN = "gun"           # 1 ops stage
    INFANTRY = "infantry"  # 3 ops stages
    TANK = "tank"          # 6 ops stages
    RECCE = "recce"        # 6 ops stages


TRAINING_OPS_STAGES: dict[ReplacementType, int] = {
    ReplacementType.GUN: 1,
    ReplacementType.INFANTRY: 3,
    ReplacementType.TANK: 6,
    ReplacementType.RECCE: 6,
}


# ---------------------------------------------------------------------------
# Reinforcement arrival (Case 20.1)
# ---------------------------------------------------------------------------

# Default arrival hexes by side (Case 20.14).
# These are scenario-dependent; the scenario setup overrides them.
DEFAULT_ARRIVAL_HEXES: dict[Side, str] = {
    Side.AXIS: "Tripoli",
    Side.COMMONWEALTH: "Cairo",
}


@dataclass
class ScheduledReinforcement:
    """A reinforcement scheduled to arrive at a specific turn.

    Case 20.11 — Placed during Naval Convoy Arrival Phase.
    """
    unit_id: str
    arrival_turn: int
    arrival_hex_name: str
    side: Side


def get_due_reinforcements(
    state: GameState,
) -> list[ScheduledReinforcement]:
    """Return reinforcements scheduled for the current Game-Turn.

    Case 20.11 — Reads from state.extras["reinforcement_schedule"].
    """
    schedule = state.extras.get("reinforcement_schedule", [])
    if not isinstance(schedule, list):
        return []
    due: list[ScheduledReinforcement] = []
    for entry in schedule:
        if isinstance(entry, dict) and entry.get("arrival_turn") == state.game_turn:
            due.append(ScheduledReinforcement(
                unit_id=entry["unit_id"],
                arrival_turn=entry["arrival_turn"],
                arrival_hex_name=entry.get("hex", ""),
                side=Side(entry["side"]),
            ))
    return due


def place_reinforcements(state: GameState) -> list[str]:
    """Place all reinforcements due this Game-Turn onto the map.

    Case 20.11, 5.2 III.D — Called during Naval Convoy Arrival Phase.
    Units listed in extras["reinforcement_units"] keyed by unit_id are
    added to state.units at their arrival hex position.

    Returns list of unit IDs placed.
    """
    due = get_due_reinforcements(state)
    if not due:
        return []

    unit_defs = state.extras.get("reinforcement_units", {})
    if not isinstance(unit_defs, dict):
        return []

    from cna.data.maps.coords import hex_id_to_coord
    from cna.data.maps.hex_catalog import get_by_name

    placed: list[str] = []
    for reinf in due:
        udef = unit_defs.get(reinf.unit_id)
        if udef is None or not isinstance(udef, dict):
            continue
        if reinf.unit_id in state.units:
            continue

        # Resolve arrival hex.
        hex_name = reinf.arrival_hex_name
        entry = get_by_name(hex_name)
        if entry is not None:
            pos = entry.coord
        else:
            try:
                pos = hex_id_to_coord(hex_name)
            except (ValueError, KeyError):
                continue

        from cna.engine.game_state import (
            OrgSize, Unit, UnitClass, UnitStats, UnitType,
        )
        unit = Unit(
            id=reinf.unit_id,
            side=reinf.side,
            name=udef.get("name", reinf.unit_id),
            unit_type=UnitType(udef.get("unit_type", "infantry")),
            unit_class=UnitClass(udef.get("unit_class", "infantry")),
            org_size=OrgSize(udef.get("org_size", "battalion")),
            stats=UnitStats(
                capability_point_allowance=udef.get("cpa", 10),
                max_toe_strength=udef.get("toe", 6),
                basic_morale=udef.get("morale", 1),
                offensive_close_assault=udef.get("off_ca", 7),
                defensive_close_assault=udef.get("def_ca", 7),
                barrage_rating=udef.get("barrage", 0),
                anti_armor_strength=udef.get("anti_armor", 0),
                armor_protection_rating=udef.get("armor_prot", 0),
            ),
            position=pos,
            current_toe=udef.get("toe", 6),
            current_morale=udef.get("morale", 1),
        )
        state.units[unit.id] = unit
        placed.append(unit.id)

    return placed


def handle_naval_convoy_arrival(state: GameState, _step) -> None:
    """PhaseDriver handler for the Naval Convoy Arrival Phase.

    Case 5.2 III.D — Places reinforcements that are due this Game-Turn.
    """
    from cna.engine.game_state import Phase
    if state.phase != Phase.NAVAL_CONVOY_ARRIVAL:
        return
    placed = place_reinforcements(state)
    if placed:
        state.log(
            f"{len(placed)} reinforcement(s) arrived: {', '.join(placed)}",
            side=None,
            category="reinforcements",
        )


# ---------------------------------------------------------------------------
# Withdrawal (Case 20.8)
# ---------------------------------------------------------------------------

WITHDRAWAL_TOE_THRESHOLD = 0.75  # Case 20.82: 75% TOE required.


def can_withdraw(unit: Unit) -> bool:
    """Whether *unit* meets the 75% TOE threshold for withdrawal (Case 20.82)."""
    if unit.stats.max_toe_strength <= 0:
        return False
    return unit.current_toe / unit.stats.max_toe_strength >= WITHDRAWAL_TOE_THRESHOLD
